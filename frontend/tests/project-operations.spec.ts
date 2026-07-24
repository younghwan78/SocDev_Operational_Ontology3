import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { resetProjectFixtures, resetReplayCase } from "./global-setup";

const frontend = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const root = path.dirname(frontend);

test.describe.configure({ mode: "serial" });

test.beforeEach(() => {
  resetProjectFixtures(root);
  resetReplayCase(root, "CASE-HO-002");
});

test("Local UX Release traces Project Risk through advice, outcome, and return", async ({ page }) => {
  const consoleProblems: string[] = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleProblems.push(`${message.type()}: ${message.text()}`);
    }
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/projects");

  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "본문으로 건너뛰기" })).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("#main-content")).toBeFocused();
  await expect(page.getByRole("heading", { name: "지금 먼저 확인할 순서" })).toBeVisible();
  const projectCard = page
    .getByRole("article")
    .filter({ hasText: "차기 Multimedia SoC Pre-silicon HW Closure" })
    .first();
  await expect(projectCard.getByText("진행 막힘", { exact: true })).toBeVisible();
  await expect(projectCard.getByText("최상위 Risk")).toBeVisible();
  await expect(projectCard.getByText("HW Architecture Freeze", { exact: true })).toBeVisible();
  await expect(projectCard.getByText("M-V-ARCH-FREEZE", { exact: true })).toHaveCount(0);
  await projectCard.getByRole("link", { name: /과제 상황 보기/ }).click();

  await expect(page).toHaveURL(/\/projects\/PROJECT-V$/);
  await expect(page.getByRole("heading", { name: "지금 가장 먼저 확인할 이유" })).toBeVisible();
  await expect(page.getByRole("list", { name: "주의 판정 근거" })).toContainText("변경안 pre-silicon workload 검증");
  await expect(page.getByRole("list", { name: "주의 판정 근거" })).not.toContainText("WORK-V-PRESI-VERIFY");
  await expect(page.getByText("공유 emulator 예약 충돌", { exact: true }).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "가장 먼저 볼 Risk와 그 근거" })).toBeVisible();
  await page.getByRole("link", { name: "근거·영향·대응 상세 추적" }).click();

  await expect(page.getByRole("heading", { name: "이 Risk는 어디에서 나왔는가" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "근거에서 무엇을 추론했고 왜 먼저 보는가" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "어떤 작업과 기준점이 영향을 받는가" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "어떤 Decision과 Action으로 위험을 제한하는가" })).toBeVisible();
  await expect(page.getByText("동일 조건을 보장하지 않는다", { exact: false })).toBeVisible();

  await page.getByRole("link", { name: "Decision 검토 열기" }).click();
  await expect(page).toHaveURL(/\/decisions\/CASE-HO-002\?from_project=PROJECT-V&from_risk=RISK-V-WRONG-COMMIT/);
  await expect(page.getByRole("link", { name: "← Risk 상세" })).toBeVisible();
  await expect(page.getByText("Silicon 이후 측정 가능한 비가역 변경 검토").first()).toBeVisible();

  await page.getByRole("button", { name: "조언 영향 평가" }).click();
  await expect(page).toHaveURL(/interaction=evaluation/);
  const initial = page.getByRole("group", { name: "1. 조언을 보기 전 내 판단" });
  const initialOption = await initial.getByLabel("선택지").locator("option").nth(1).getAttribute("value");
  expect(initialOption).toBeTruthy();
  await initial.getByLabel("선택지").selectOption(initialOption ?? "");
  await initial.getByLabel("감수할 위험").fill("비가역 interface 변경의 silicon 이후 실패");
  await initial.getByLabel("필요한 보호 조치").fill("변경 범위 제한과 sign-off 실패 시 제외");
  await initial.getByLabel("판단 이유").fill("현재 근거만으로 전체 변경을 확정하지 않습니다.");
  await initial.getByRole("button", { name: "사전 판단을 변경 불가로 기록" }).click();

  await page.getByRole("button", { name: "가상 역할 검토 실행", exact: true }).click();
  for (let attempt = 0; attempt < 20; attempt += 1) {
    execFileSync("uv", ["run", "python", "-m", "soc_ot.worker", "--once"], {
      cwd: root,
      stdio: "ignore",
    });
    await page.waitForTimeout(200);
    const progress = await page.getByText(/관점별 검토:/).locator("..").textContent();
    if (progress?.includes("완료")) break;
  }
  await expect(page.getByText(/관점별 검토:/).locator("..")).toContainText("완료");
  await page.getByRole("button", { name: "가상 최종 판단 실행" }).click();
  await expect(page.getByRole("button", { name: "조언 공개 시점 기록" })).toBeVisible();
  await page.getByRole("button", { name: "조언 공개 시점 기록" }).click();

  const advice = page
    .getByRole("heading", { name: "가상 조언 공개 완료" })
    .locator("..");
  const advisedOptionTitle = await advice.locator("strong").textContent();
  expect(advisedOptionTitle).toBeTruthy();
  const final = page.getByRole("group", { name: "3. 조언을 본 뒤 최종 판단" });
  const advisedOption = final.locator("option").filter({ hasText: advisedOptionTitle ?? "" });
  const finalOption = await advisedOption.count() > 0
    ? await advisedOption.first().getAttribute("value")
    : initialOption;
  await final.getByLabel("선택지").selectOption(finalOption ?? "");
  await final.getByLabel("감수할 위험").fill("검증 전 변경의 잔여 위험");
  await final.getByLabel("필요한 보호 조치").fill("최소 근거 확보와 rollback 조건 유지");
  await final.getByLabel("판단 이유").fill("가상 조언의 선택과 보호 조건을 수용합니다.");
  await final.getByRole("button", { name: "최종 판단을 변경 불가로 기록" }).click();
  await expect(page.getByRole("heading", { name: "3. 최종 판단 · 수용" })).toBeVisible();

  await page.getByRole("button", { name: "다음 Simulation Step 진행" }).click();
  await expect(page.getByRole("heading", { name: "예상과 실제를 분리해서 비교합니다" })).toBeVisible();
  await page.getByRole("button", { name: "판단 평가 보기" }).click();
  await expect(page.getByRole("heading", { name: "다음 판단에 남길 학습" })).toBeVisible();
  await expect(page.getByText("이번 fixture 결과에 기록된 추가 학습은 없습니다.")).toBeVisible();
  await page.getByRole("button", { name: "학습 요약 보기" }).click();
  await expect(page.locator("#learning")).toBeFocused();
  await page.getByRole("link", { name: "← Risk 상세" }).click();
  await expect(page).toHaveURL(/\/projects\/PROJECT-V\/risks\/RISK-V-WRONG-COMMIT$/);

  const hasPageOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasPageOverflow).toBe(false);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  expect(consoleProblems).toEqual([]);
});

test("Project Step 20 stays responsive and does not reveal Step 21 information", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/projects/PROJECT-V?at_step=20");

  await expect(page.getByText("선택한 Step 당시 상태")).toBeVisible();
  await expect(page.getByText("공유 emulator 예약 충돌", { exact: false })).toHaveCount(0);
  await expect(page.getByText("RISK-V-RESOURCE-CONFLICT", { exact: false })).toHaveCount(0);
  await page.getByRole("link", { name: "근거·영향·대응 상세 추적" }).click();
  await expect(page).toHaveURL(/at_step=20/);
  await expect(page.getByText("선택한 Step 당시 Risk")).toBeVisible();

  const decisionLink = page.getByRole("link", { name: "Decision 검토 열기" });
  await expect(decisionLink).toHaveAttribute(
    "href",
    "/decisions/CASE-HO-002?from_project=PROJECT-V&from_risk=RISK-V-WRONG-COMMIT&from_project_step=20",
  );
  await expect(decisionLink).not.toHaveAttribute("href", /at_step/);

  const hasPageOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasPageOverflow).toBe(false);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});
