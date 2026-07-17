import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

import { resetReplayCase } from "./global-setup";

const frontend = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const root = path.dirname(frontend);

test.describe.configure({ mode: "serial" });

test.beforeEach(() => {
  resetReplayCase(root, "CASE-VR-001");
});

test("decision inbox prioritizes the next decision at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/decisions");

  await expect(page.getByRole("heading", { name: "지금 확인할 결정" })).toBeVisible();
  const card = page.getByRole("article").filter({ hasText: "UHD60 EIS 전력 여유 검토" });
  await expect(card.getByText("왜 지금")).toBeVisible();
  await expect(card.getByRole("link", { name: "결정 검토" })).toBeVisible();
  await expect(page.getByText("CASE-VR-001")).toHaveCount(0);
  const hasPageOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasPageOverflow).toBe(false);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});

test("CASE-VR-001 complete Replay decision workflow is accessible", async ({ page }) => {
  const consoleProblems: string[] = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleProblems.push(`${message.type()}: ${message.text()}`);
    }
  });
  await page.goto("/decisions");
  await expect(page.getByRole("heading", { name: "지금 확인할 결정" })).toBeVisible();
  const targetCard = page
    .getByRole("article")
    .filter({ hasText: "UHD60 EIS 전력 여유 검토" });
  await expect(targetCard.getByText(/Architecture Freeze까지 1 Step/)).toBeVisible();
  await targetCard.getByRole("link", { name: "결정 검토" }).click();

  await expect(page.getByText("UHD60 EIS 전력 여유 검토")).toBeVisible();
  await expect(page.getByRole("heading", { name: /UHD60 EIS/ }).first()).toBeVisible();
  await expect(page.getByText("Step 13 · Architecture Freeze")).toBeVisible();
  await expect(page.getByRole("heading", { name: "선택한 시점의 개발 상태와 변화 원인" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "가장 가까운 Commitment Window" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "선택지별 예상 상태 변화" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "같은 기준으로 선택지를 비교합니다" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "확인된 사실" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "근거 기반 추론" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "검토할 가정" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "아직 모름" })).toBeVisible();
  await expect(page.getByText("실행 한도:")).toHaveCount(0);
  await expect(page.getByText("관측", { exact: true })).toBeVisible();
  await expect(
    page
      .getByLabel("선택지별 예상 상태 변화")
      .getByRole("heading", { name: "SW feature flag로 제한 진행" }),
  ).toBeVisible();

  await expect(page.locator(".primary-button")).toHaveCount(1);
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
  await expect(page.getByRole("heading", { name: "의견 일치" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "핵심 이견" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "확인 필요" })).toBeVisible();
  await page.getByText("Role별 원문 보기").click();
  await expect(page.getByText(/정성적 확신 수준:/).first()).toBeVisible();
  await expect(page.getByText("ROLE-ARCH", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "가상 최종 판단 실행" }).click();
  await expect(page.getByRole("heading", { name: "판단에서 실행과 확인까지 한 흐름으로 봅니다" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "안전 조건과 Rollback" })).toBeVisible();
  await expect(page.getByText(/20 GB\/s/).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "결정이 만든 실제 상태 변화" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "아직 남는 위험" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "결과는 다음 Simulation Step 전까지 숨겨집니다" })).toBeVisible();
  await expect(page.locator(".primary-button")).toHaveCount(1);

  await page.getByRole("button", { name: "다음 Simulation Step 진행" }).click();
  await expect(page.getByRole("heading", { name: "예상과 실제를 분리해서 비교합니다" })).toBeVisible();
  await expect(page.getByText(/실행된 보호 조치:/).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "보호 조치 결과" })).toBeVisible();
  await page.getByRole("button", { name: "판단 평가 보기" }).click();
  await expect(page.getByRole("heading", { name: "당시 판단은 적절했는가" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "위험을 실제로 제한했는가" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "다음 판단에 남길 학습" })).toBeVisible();
  await expect(page.getByText("DDR_BANDWIDTH", { exact: false })).toHaveCount(0);

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  expect(consoleProblems).toEqual([]);
  await page.screenshot({
    path: path.join(root, "output/playwright/e2e-complete-workflow.png"),
    fullPage: true,
  });
});

test("workspace remains usable at 390px", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/decisions/CASE-VR-001");
  await expect(page.getByRole("heading", { name: "선택한 시점의 개발 상태와 변화 원인" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "같은 기준으로 선택지를 비교합니다" })).toBeVisible();
  const mobileCard = page.locator(".mobile-option-card");
  await expect(mobileCard).toContainText("SW feature flag로 제한 진행");
  await page.getByRole("button", { name: "다음 선택지" }).click();
  await expect(mobileCard).toContainText("측정 완료까지 EIS 연기");
  await page.getByLabel("관찰 시점").selectOption("9");
  await expect(page.getByText("선택한 Step의 당시 개발 상태")).toBeVisible();
  await expect(page.getByText("과거 Step에서는 실행할 수 없습니다.")).toBeVisible();
  await expect(page.getByRole("heading", { name: "아직 Role 의견 종합이 없습니다" })).toBeVisible();
  await expect(page.getByText("Role별 원문 보기")).toHaveCount(0);
  const hasPageOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasPageOverflow).toBe(false);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});
