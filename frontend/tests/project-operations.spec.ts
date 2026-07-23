import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
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

test("Project Operations traces portfolio priority through Risk and Decision", async ({ page }) => {
  const consoleProblems: string[] = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleProblems.push(`${message.type()}: ${message.text()}`);
    }
  });

  await page.setViewportSize({ width: 1440, height: 1000 });
  await page.goto("/projects");

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
