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
  await page.screenshot({
    path: path.join(root, "output/playwright/inbox-390px.png"),
    fullPage: true,
  });
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
  await expect(page.getByText(/대기 원인:/).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "선택한 시점의 개발 상태와 변화 원인" })).toBeVisible();
  await expect(page.getByRole("heading", { name: /Step 12 개발 상태/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "무엇이 바뀌었고 어디까지 영향을 주는가" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "가장 가까운 선택 가능 기한(Commitment Window)" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "선택지별 예상 상태 변화" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "같은 기준으로 선택지를 비교합니다" })).toBeVisible();
  await expect(page.getByText("가역성", { exact: true }).first()).toBeVisible();
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
  await expect(page.locator("details.role-originals")).not.toHaveAttribute("open", "");
  await expect(page.getByText(/정성적 확신 수준:/).first()).not.toBeVisible();
  await expect(page.getByText("ROLE-ARCH", { exact: true })).toHaveCount(0);
  await page.getByRole("button", { name: "가상 최종 판단 실행" }).click();
  await expect(page.getByRole("heading", { name: "판단에서 실행과 확인까지 한 흐름으로 봅니다" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "안전 조건과 되돌리기(Rollback)" })).toBeVisible();
  await expect(page.getByText(/20 GB\/s/).first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "결정이 만든 실제 상태 변화" })).toBeVisible();
  await expect(page.locator(".observed-progress")).toContainText("행동");
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
  await expect(page.locator("details.role-originals[open]")).toHaveCount(0);

  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  expect(consoleProblems).toEqual([]);
  await page.screenshot({
    path: path.join(root, "output/playwright/e2e-complete-workflow.png"),
    fullPage: true,
  });
});

test("evaluation mode preserves pre-advice judgment and measures advice adoption", async ({ page }) => {
  const consoleProblems: string[] = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleProblems.push(`${message.type()}: ${message.text()}`);
    }
  });
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/decisions/CASE-VR-001?interaction=evaluation");

  await expect(page.getByRole("heading", {
    name: "내 판단과 가상 조언을 분리해 기록합니다",
  })).toBeVisible();
  await expect(page.getByRole("heading", { name: "의견 일치" })).toHaveCount(0);
  const initial = page.getByRole("group", { name: "1. 조언을 보기 전 내 판단" });
  await initial.getByLabel("선택지").selectOption("OPT-SW-GUARDED");
  await initial.getByLabel("감수할 위험").fill("장시간 thermal 거동");
  await initial.getByLabel("필요한 보호 조치").fill("feature flag로 즉시 철회");
  await initial.getByLabel("판단 이유").fill("Freeze 전에 가역 경로를 확보합니다.");
  await initial.getByRole("button", { name: "사전 판단을 변경 불가로 기록" }).click();
  await expect(page.getByRole("heading", { name: "1. 조언 전 판단 · 기록 완료" })).toBeVisible();

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
  await expect(page.getByRole("heading", { name: "의견 일치" })).toHaveCount(0);
  await page.getByRole("button", { name: "가상 최종 판단 실행" }).click();

  await expect(page.getByRole("button", { name: "조언 공개 시점 기록" })).toBeVisible();
  await expect(page.getByRole("heading", {
    name: "판단에서 실행과 확인까지 한 흐름으로 봅니다",
  })).toHaveCount(0);
  await page.getByRole("button", { name: "조언 공개 시점 기록" }).click();
  await expect(page.getByRole("heading", {
    name: "판단에서 실행과 확인까지 한 흐름으로 봅니다",
  })).toBeVisible();
  await expect(page.getByRole("heading", { name: "가상 조언 공개 완료" })).toBeVisible();

  const final = page.getByRole("group", { name: "3. 조언을 본 뒤 최종 판단" });
  await final.getByLabel("선택지").selectOption("OPT-SW-GUARDED");
  await final.getByLabel("감수할 위험").fill("장시간 thermal 거동");
  await final.getByLabel("필요한 보호 조치").fill("Step 15 실측과 rollback");
  await final.getByLabel("판단 이유").fill("조언의 가역 경로와 중단 기준을 수용합니다.");
  await final.getByRole("button", { name: "최종 판단을 변경 불가로 기록" }).click();
  await expect(page.getByRole("heading", { name: "3. 최종 판단 · 수용" })).toBeVisible();
  await expect(page.getByText(/simulated Chair의 판단이나 실행 계획을 변경하지 않습니다/)).toBeVisible();

  await page.reload();
  await expect(page.getByRole("heading", { name: "3. 최종 판단 · 수용" })).toBeVisible();
  const hasPageOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasPageOverflow).toBe(false);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  expect(consoleProblems).toEqual([]);
  await page.screenshot({
    path: path.join(root, "output/playwright/ux-j-evaluation-390px.png"),
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
  await expect(page.getByRole("heading", { name: "아직 역할별 의견 종합이 없습니다" })).toBeVisible();
  await expect(page.getByText("역할별 원문 보기")).toHaveCount(0);
  const hasPageOverflow = await page.evaluate(
    () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
  );
  expect(hasPageOverflow).toBe(false);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
  await page.screenshot({
    path: path.join(root, "output/playwright/workspace-390px.png"),
    fullPage: true,
  });
});

test("workspace URL preserves the selected step and mobile alternative", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/decisions/CASE-VR-001");

  const mobileCard = page.locator(".mobile-option-card");
  await page.getByRole("button", { name: "다음 선택지" }).click();
  await expect(mobileCard).toContainText("측정 완료까지 EIS 연기");
  const selectedOption = new URL(page.url()).searchParams.get("option");
  expect(selectedOption).toBe("2");
  await page.getByLabel("관찰 시점").selectOption("9");
  await expect(page).toHaveURL(/at_step=9/);
  await expect(page).toHaveURL(new RegExp(`option=${selectedOption}`));

  await page.reload();
  await expect(page.getByText("선택한 Step의 당시 개발 상태")).toBeVisible();
  await expect(mobileCard).toContainText("측정 완료까지 EIS 연기");

  await page.goBack();
  await expect(page).not.toHaveURL(/at_step=9/);
  await expect(page).toHaveURL(new RegExp(`option=${selectedOption}`));
  await expect(page.getByRole("button", { name: "가상 역할 검토 실행", exact: true })).toBeVisible();

  await page.goBack();
  await expect(page).not.toHaveURL(/option=/);
  await expect(mobileCard).toContainText("SW feature flag로 제한 진행");

  await page.goForward();
  await expect(page).toHaveURL(/option=2/);
  await expect(mobileCard).toContainText("측정 완료까지 EIS 연기");

  await page.goForward();
  await expect(page).toHaveURL(/at_step=9/);
  await expect(page.getByText("선택한 Step의 당시 개발 상태")).toBeVisible();
});

test("workspace reflows at 768px and a 200-percent equivalent viewport", async ({ page }) => {
  for (const viewport of [
    { width: 768, height: 1024, label: "tablet" },
    { width: 640, height: 900, label: "200-percent" },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto("/decisions/CASE-VR-001");
    await expect(page.getByRole("heading", { name: "선택한 시점의 개발 상태와 변화 원인" })).toBeVisible();
    await expect(page.getByRole("button", { name: "가상 역할 검토 실행", exact: true })).toBeVisible();
    const hasPageOverflow = await page.evaluate(
      () => document.documentElement.scrollWidth > document.documentElement.clientWidth,
    );
    expect(hasPageOverflow, `${viewport.label} viewport overflow`).toBe(false);
    const accessibility = await new AxeBuilder({ page }).analyze();
    expect(accessibility.violations).toEqual([]);
    await page.screenshot({
      path: path.join(root, `output/playwright/workspace-${viewport.label}.png`),
      fullPage: true,
    });
  }
});

test("keyboard and screen-reader semantics expose a direct main-content path", async ({ page }) => {
  await page.setViewportSize({ width: 768, height: 1024 });
  await page.goto("/decisions/CASE-VR-001");

  await page.keyboard.press("Tab");
  const skipLink = page.getByRole("link", { name: "본문으로 건너뛰기" });
  await expect(skipLink).toBeFocused();
  await expect(skipLink).toBeVisible();
  await page.keyboard.press("Enter");
  await expect(page.locator("main#main-content")).toBeFocused();
  await expect(page.locator("main")).toHaveCount(1);
  await expect(page.getByRole("navigation", { name: "결정 검토 문맥" })).toBeVisible();

  const primaryAction = page.getByRole("button", { name: "가상 역할 검토 실행", exact: true });
  await primaryAction.focus();
  await expect(primaryAction).toBeFocused();
  await expect(primaryAction).toHaveCSS("outline-style", "solid");
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});

test("partial role review keeps completed perspectives and gives a recovery action", async ({ page }) => {
  const partialRun = {
    run_id: "RUN-UX-F-PARTIAL",
    status: "PARTIALLY_COMPLETED",
    error_code: null,
    result: {
      dossier: {
        original_reviews: [
          { role_id: "architecture_system" },
          { role_id: "verification_measurement" },
          { role_id: "program_risk" },
        ],
      },
      failed_roles: [
        { role_id: "sw", error_code: "PROVIDER_ATTEMPT_FAILED", provider_attempts: 1 },
      ],
    },
  };
  await page.route("**/api/v1/decision-cases/CASE-VR-001/review-runs", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(partialRun) });
      return;
    }
    await route.fallback();
  });
  await page.route("**/api/v1/runs/RUN-UX-F-PARTIAL", async (route) => {
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(partialRun) });
  });

  await page.goto("/decisions/CASE-VR-001");
  await page.getByRole("button", { name: "가상 역할 검토 실행", exact: true }).click();
  await expect(page.getByText(/관점별 검토:/).locator("..")).toContainText("일부 완료");
  await expect(page.getByText(/완료:/).locator("..")).toContainText("Architecture");
  await expect(page.getByText(/실패:/).locator("..")).toContainText("SW/FW/HAL · 응답 검증 실패");
  await expect(page.getByText("PROVIDER_ATTEMPT_FAILED", { exact: false })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "가상 역할 검토 재시도" })).toBeVisible();
  await expect(page.getByRole("button", { name: "가상 최종 판단 실행" })).toHaveCount(0);
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});

test("aggregate conflict announces stale state and restores the current workspace", async ({ page }) => {
  await page.route("**/api/v1/decision-cases/CASE-VR-001/review-runs", async (route) => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 409,
        contentType: "application/json",
        body: JSON.stringify({ detail: { code: "CASE_VERSION_CONFLICT" } }),
      });
      return;
    }
    await route.fallback();
  });

  await page.goto("/decisions/CASE-VR-001");
  await page.getByRole("button", { name: "가상 역할 검토 실행", exact: true }).click();
  const staleAlert = page.getByRole("alert").filter({ hasText: "개발 상태가 변경되었습니다" });
  await expect(staleAlert).toBeVisible();
  await expect(page.locator(".brief-primary-action")).toBeDisabled();
  await staleAlert.getByRole("button", { name: "최신 상태 불러오기" }).click();
  await expect(staleAlert).toHaveCount(0);
  await expect(page.getByRole("button", { name: "가상 역할 검토 실행", exact: true })).toBeEnabled();
});
