# DSA V137 事件数据可用性与冷启动提速实施计划

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让公开事件观察在服务重启后优先读取安全磁盘快照，并以单飞后台任务独立刷新 A 股、港股和美股数据，避免慢源阻塞首页。

**Architecture:** V137 在 V136 观察服务外增加版本化、原子写入、严格校验的公开快照存储。端点采用 cache-first：内存或磁盘快照立即返回，缺少快照时返回明确的刷新状态并后台构建；事件候选按市场独立抓取，任何单一市场失败只影响该市场。前端显示三市场可用性、缓存来源和后台刷新状态，并在刷新完成前有限轮询。

**Tech Stack:** Python 3.11、FastAPI、Pydantic、`concurrent.futures`、React 18、TypeScript、Vitest、Playwright。

---

### Task 1: 持久公开快照和单飞刷新

**Files:**
- Create: `src/services/public_event_reaction_cache.py`
- Modify: `src/services/public_market_event_reaction_service.py`
- Create: `tests/test_public_event_reaction_cache_v137.py`
- Modify: `tests/test_public_market_event_reaction_service_v136.py`

- [x] **Step 1: 写失败测试**

测试必须证明：

```python
store.write(payload)
restarted = PublicEventReactionSnapshotStore(path=path)
assert restarted.read()["payload"]["items"] == payload["items"]
assert restarted.read()["payload"]["ai_used"] is False
assert restarted.read()["payload"]["informational_only"] is True
```

并覆盖损坏 JSON、错误版本、超限文件、密钥字段、原子临时文件、过期快照、单飞后台刷新和刷新失败保留旧快照。

- [x] **Step 2: 运行红灯测试**

Run:

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_event_reaction_cache_v137
```

Expected: FAIL，因为存储模块和 cache-first 接口尚不存在。

- [x] **Step 3: 实现最小安全存储**

存储文件格式固定为：

```json
{
  "version": 1,
  "written_at": 1785388800.0,
  "payload": {
    "as_of": "2026-07-30T00:00:00+00:00",
    "items": [],
    "market_sources": [],
    "warnings": [],
    "cache": {
      "hit": true,
      "age_seconds": 0,
      "ttl_seconds": 900,
      "storage": "disk",
      "refreshing": false
    },
    "ai_used": false,
    "informational_only": true
  }
}
```

只允许 V137 响应字段；拒绝 `api_key`、`token`、`authorization`、`cookie`、`user_id`、`email` 和异常边界值。写入使用同目录临时文件后 `Path.replace()`，最大文件 1 MiB。

- [x] **Step 4: 实现 cache-first 与单飞刷新**

`build(cache_first=True)` 的顺序为：

1. 返回新鲜内存缓存。
2. 返回有效磁盘快照；陈旧但未超过保留期时标记 `stale` 并启动后台刷新。
3. 无快照时立即返回 `refreshing=true` 的空响应并启动后台刷新。
4. 同一时刻最多一个刷新任务；刷新成功替换内存和磁盘，失败保留旧快照并记录降级。

- [x] **Step 5: 运行绿灯测试**

Run:

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_event_reaction_cache_v137 tests.test_public_market_event_reaction_service_v136
```

Expected: PASS。

### Task 2: 三市场独立事件候选与来源状态

**Files:**
- Modify: `api/v1/endpoints/market_workspace.py`
- Modify: `src/services/public_market_calendar_service.py`
- Modify: `api/v1/schemas/market_workspace.py`
- Create: `tests/test_public_event_reaction_availability_v137.py`
- Modify: `tests/test_public_market_event_reaction_api_v136.py`

- [x] **Step 1: 写失败测试**

测试分别令 A 股、港股或美股源超时，断言其他市场事件仍保留，并返回：

```python
{
    "market": "hk",
    "status": "unavailable",
    "event_count": 0,
    "observed_at": None,
    "warning_code": "event_calendar_market_unavailable",
}
```

另验证同一日历 key 的未完成 Future 会被复用，不因重复请求持续堆积。

- [x] **Step 2: 运行红灯测试**

Run:

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_event_reaction_availability_v137
```

Expected: FAIL，因为 V136 尚无 `market_sources` 和独立市场加载。

- [x] **Step 3: 实现独立市场加载**

端点为 `cn`、`hk`、`us` 分别提交事件日历任务，使用公开覆盖样本作为冷启动候选；可用的市场首页缓存仅用于补充符号，不触发完整首页同步构建。每个市场独立记录 `fresh/cached/stale/unavailable`、事件数、抓取时间和警告码。

- [x] **Step 4: 实现日历任务复用**

日历服务按 cache key 保存尚未完成的 Future。超时只返回当前可用结果，不重复提交相同任务；任务完成后由下一次读取收割并写入原有有界内存缓存。

- [x] **Step 5: 运行绿灯测试**

Run:

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_event_reaction_availability_v137 tests.test_public_market_event_reaction_api_v136 tests.test_public_market_calendar_service_v135
```

Expected: PASS。

### Task 3: 启动预热与公开端点

**Files:**
- Modify: `api/app.py`
- Modify: `api/v1/endpoints/market_workspace.py`
- Modify: `.env.example`
- Modify: `docs/superpowers/platform-production-env.example`
- Modify: `.env` (ignored local configuration only)
- Create: `tests/test_public_event_reaction_startup_v137.py`

- [x] **Step 1: 写失败测试**

断言 FastAPI lifespan 只在 V136/V137 本地开关开启时安排一次预热，退出时不泄漏应用级任务；生产模板保持关闭，默认缓存路径为 `local/public_event_reactions_v137.json`。

- [x] **Step 2: 实现启动预热**

启动只触发公开、无密钥、无用户数据的单飞刷新。它不启动 Windows 自动服务、不访问支付、不读取平台或 BYOK 密钥；端点无快照时仍在 5 秒内返回刷新状态。

- [x] **Step 3: 验证**

Run:

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_event_reaction_startup_v137 tests.test_public_market_event_reaction_api_v136
```

Expected: PASS。

### Task 4: 前端三市场可用性与自动回填

**Files:**
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/components/market-home/MarketEventReactionPanelV136.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/MarketEventReactionPanelV136.test.tsx`
- Modify: `apps/dsa-web/src/api/__tests__/marketWorkspace.test.ts`

- [x] **Step 1: 写失败测试**

测试中文和英文状态条、磁盘缓存、后台刷新、单市场降级、保留成功市场数据、最多六轮自动轮询、卸载后停止轮询，以及 `aiUsed=true` 或 `informationalOnly=false` 时继续失败关闭。

- [x] **Step 2: 运行红灯测试**

Run:

```powershell
npm.cmd run test -- --run src/api/__tests__/marketWorkspace.test.ts src/components/market-home/__tests__/MarketEventReactionPanelV136.test.tsx
```

Expected: FAIL，因为页面尚未展示 V137 状态。

- [x] **Step 3: 实现状态条和有限轮询**

三市场状态使用紧凑列表，不增加营销卡片。后台刷新时每 2 秒重读一次，最多六次；任一市场成功数据始终可见。所有文案跟随系统语言。

- [x] **Step 4: 运行绿灯测试**

Run:

```powershell
npm.cmd run test -- --run src/api/__tests__/marketWorkspace.test.ts src/components/market-home/__tests__/MarketEventReactionPanelV136.test.tsx
```

Expected: PASS。

### Task 5: V137 门禁、文档和发布包

**Files:**
- Create: `scripts/verify_platform_event_data_availability_v137.py`
- Create: `tests/test_platform_event_data_availability_v137_verifier.py`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `.gitignore`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] **Step 1: 添加 verifier 失败测试**

Verifier 必须检查持久缓存安全边界、单飞刷新、三市场状态、生产默认关闭、前端中英文和发布包分类。

- [x] **Step 2: 实现 verifier**

成功标记：

```text
DSA_PLATFORM_EVENT_DATA_AVAILABILITY_V137_OK
```

- [x] **Step 3: 更新文档**

明确 V137 只提供公开资讯和历史数据；事件同期表现不证明因果关系，不构成投资建议。记录实时源不可用时的真实降级，不把测试夹具描述为实时市场成功。

### Task 6: 全量验收、本地提交和干净树

**Files:**
- Verify only

- [x] **Step 1: 运行后端、前端和历史门禁**

运行 V126-V137 聚焦后端测试、全量 Vitest、lint、build、V126-V137 verifier、V1 operability、V2 readiness 和 release-package verifier。

- [x] **Step 2: 重启并测量**

预热后重启 8018，验证 `/health` 200；磁盘缓存请求目标低于 2 秒，无缓存请求目标低于 5 秒返回 `refreshing`；后台完成后至少保留成功市场数据并如实显示其他市场状态。

- [x] **Step 3: 浏览器验收**

在桌面和移动宽度验收中文、英文、三市场状态、窗口切换、个股查询入口、降级提示、无横向溢出和无空白页。

- [x] **Step 4: 安全和 Git 收口**

运行敏感密钥扫描、`git diff --check`，显式暂存 V137 文件并本地提交。最终 `git status --short --untracked-files=all` 必须为空；不推送、不删除数据库、历史报告或用户数据。
