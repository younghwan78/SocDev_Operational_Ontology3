import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";

const frontend = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
const root = path.dirname(frontend);

test.describe.configure({ mode: "serial" });

test("CASE-VR-001 complete Replay decision workflow is accessible", async ({ page }) => {
  const consoleProblems: string[] = [];
  page.on("console", (message) => {
    if (["error", "warning"].includes(message.type())) {
      consoleProblems.push(`${message.type()}: ${message.text()}`);
    }
  });
  await page.goto("/decisions");
  await page
    .getByRole("article")
    .filter({ hasText: "UHD60 EIS 전력 여유 검토" })
    .getByRole("link", { name: "결정 검토" })
    .click();

  await expect(page.getByRole("heading", { name: "UHD60 EIS 전력 여유 검토" })).toBeVisible();
  await expect(page.getByText("결정 기한: Step 13 · Architecture Freeze")).toBeVisible();
  await expect(page.getByRole("cell", { name: "BLOCKED" })).toBeVisible();
  await expect(page.getByText("SW feature flag로 제한 진행")).toBeVisible();
  await expect(page.getByText("현재 사용 가능").first()).toBeVisible();
  await expect(page.getByRole("heading", { name: "개발 진행 타임라인" })).toBeVisible();
  await expect(page.getByText("기록된 개발 변경 없음")).toBeVisible();

  await page.getByRole("button", { name: "역할 검토 시작", exact: true }).click();
  for (let attempt = 0; attempt < 20; attempt += 1) {
    execFileSync("uv", ["run", "python", "-m", "soc_ot.worker", "--once"], {
      cwd: root,
      stdio: "ignore",
    });
    await page.waitForTimeout(200);
    const progress = await page.locator(".run-progress p").first().textContent();
    if (progress?.includes("완료")) break;
  }
  await expect(page.locator(".run-progress p").first()).toContainText("완료", {
    timeout: 10_000,
  });

  await page.getByRole("button", { name: "다중 역할 검토 시작" }).click();
  for (let attempt = 0; attempt < 20; attempt += 1) {
    execFileSync("uv", ["run", "python", "-m", "soc_ot.worker", "--once"], {
      cwd: root,
      stdio: "ignore",
    });
    await page.waitForTimeout(200);
    const progress = await page.getByText(/다중 역할 진행:/).locator("..").textContent();
    if (progress?.includes("완료")) break;
  }
  await expect(page.getByText(/다중 역할 진행:/).locator("..")).toContainText("완료");
  await page.getByRole("button", { name: "모의 Chair 결정" }).click();
  await expect(page.getByRole("heading", { name: "다음 행동" })).toBeVisible();
  await expect(page.locator("p").filter({ hasText: "할 일:" })).toContainText(
    "OPT-SW-GUARDED",
  );
  await expect(page.locator("p").filter({ hasText: "실패 시:" })).toContainText("rollback");
  await expect(page.getByRole("heading", { name: "반대 의견" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "안전장치" })).toBeVisible();
  await expect(page.locator(".safeguard-card p").filter({ hasText: "측정 기준:" })).toContainText(
    "20 GB/s",
  );

  await page.getByRole("button", { name: "다음 Step 진행" }).click();
  await expect(
    page.locator(".decision-result p").filter({ hasText: "실행된 보호 조치:" }),
  ).toContainText("rollback");
  await page.getByRole("button", { name: "판단 품질 평가" }).click();
  await expect(page.getByRole("heading", { name: "과정 평가" })).toBeVisible();
  await expect(page.getByText("왜 과정과 결과가 다를 수 있나요?")).toBeVisible();

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
  await expect(page.getByRole("heading", { name: "현재 개발 상황" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "선택지와 되돌릴 수 있는 정도" })).toBeVisible();
  const accessibility = await new AxeBuilder({ page }).analyze();
  expect(accessibility.violations).toEqual([]);
});
