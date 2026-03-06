# 后端重构任务提示词

## 任务说明

你负责后端 API 重构工作。请按照 DDD 理念完成以下任务，确保分层清晰、职责单一。

## 任务列表

### 任务 1：创建 SignalQueryService（应用层）

**文件**: `application/signal_query_service.py`（新建）

**需求**:
封装信号查询业务逻辑，处理分页、筛选、排序

**参考实现**:
```python
"""
应用层：信号查询服务
封装信号查询的分页、筛选、排序业务逻辑
"""
from dataclasses import dataclass
from typing import List, Optional, Generic, TypeVar
from infrastructure.repo.sqlite_repo import SQLiteRepo
from core.entities import Signal

T = TypeVar('T')

@dataclass
class PaginatedResult(Generic[T]):
    """分页结果封装"""
    items: List[T]
    total: int
    page: int
    size: int
    has_next: bool
    has_prev: bool

class SignalQueryService:
    """
    信号查询应用服务
    职责：编排仓储查询，处理分页逻辑
    """

    def __init__(self, repo: SQLiteRepo):
        self.repo = repo

    async def query_signals(
        self,
        symbols: Optional[List[str]] = None,
        intervals: Optional[List[str]] = None,
        directions: Optional[List[str]] = None,
        start_time: Optional[int] = None,
        end_time: Optional[int] = None,
        min_score: Optional[int] = None,
        quality_tier: Optional[str] = None,
        page: int = 1,
        size: int = 20,
        sort_by: str = "timestamp",
        order: str = "desc"
    ) -> PaginatedResult[Signal]:
        """
        分页查询信号

        :param symbols: 币种列表
        :param intervals: 时间级别列表
        :param directions: 方向列表
        :param start_time: 开始时间（毫秒戳）
        :param end_time: 结束时间（毫秒戳）
        :param min_score: 最低评分
        :param quality_tier: 信号等级 (A/B/C)
        :param page: 页码 (从 1 开始)
        :param size: 每页大小
        :param sort_by: 排序字段
        :param order: 排序方向 (asc/desc)
        :return: 分页结果
        """
        # 调用仓储层查询
        items, total = await self.repo.query_signals_with_pagination(
            symbols=symbols,
            intervals=intervals,
            directions=directions,
            start_time=start_time,
            end_time=end_time,
            min_score=min_score,
            quality_tier=quality_tier,
            offset=(page - 1) * size,
            limit=size,
            sort_by=sort_by,
            order=order
        )

        return PaginatedResult(
            items=items,
            total=total,
            page=page,
            size=size,
            has_next=(page * size) < total,
            has_prev=page > 1
        )
```

---

### 任务 2：仓储层分页查询扩展

**文件**: `infrastructure/repo/sqlite_repo.py`

**需求**:
新增分页查询方法，支持动态筛选条件

**参考实现**:
```python
async def query_signals_with_pagination(
    self,
    symbols: Optional[List[str]] = None,
    intervals: Optional[List[str]] = None,
    directions: Optional[List[str]] = None,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    min_score: Optional[int] = None,
    quality_tier: Optional[str] = None,
    offset: int = 0,
    limit: int = 20,
    sort_by: str = "timestamp",
    order: str = "desc"
) -> Tuple[List[Signal], int]:
    """
    分页查询信号

    :return: (信号列表，总数)
    """
    async with aiosqlite.connect(self.db_path) as db:
        # 构建动态 WHERE 子句
        where_clauses = []
        params = []

        if symbols:
            placeholders = ','.join(['?' for _ in symbols])
            where_clauses.append(f"symbol IN ({placeholders})")
            params.extend(symbols)

        if intervals:
            placeholders = ','.join(['?' for _ in intervals])
            where_clauses.append(f"interval IN ({placeholders})")
            params.extend(intervals)

        if directions:
            placeholders = ','.join(['?' for _ in directions])
            where_clauses.append(f"direction IN ({placeholders})")
            params.extend(directions)

        if start_time:
            where_clauses.append("timestamp >= ?")
            params.append(start_time)

        if end_time:
            where_clauses.append("timestamp <= ?")
            params.append(end_time)

        if min_score is not None:
            where_clauses.append("score >= ?")
            params.append(min_score)

        if quality_tier:
            where_clauses.append("quality_tier = ?")
            params.append(quality_tier)

        where_sql = " AND ".join(where_clauses) if where_clauses else "1=1"

        # 查询总数
        count_sql = f"SELECT COUNT(*) FROM signals WHERE {where_sql}"
        cursor = await db.execute(count_sql, params)
        total = (await cursor.fetchone())[0]

        # 分页查询
        order_dir = "DESC" if order.lower() == "desc" else "ASC"
        sort_column = self._validate_sort_column(sort_by)  # 防止 SQL 注入

        query_sql = f"""
            SELECT id, symbol, interval, direction, entry_price, stop_loss,
                   take_profit_1, timestamp, reason, sl_distance_pct, score,
                   score_details, shadow_ratio, ema_distance, volatility_atr,
                   source, is_contrarian, quality_tier
            FROM signals
            WHERE {where_sql}
            ORDER BY {sort_column} {order_dir}
            LIMIT ? OFFSET ?
        """
        params.extend([limit, offset])

        cursor = await db.execute(query_sql, params)
        rows = await cursor.fetchall()

        signals = [self._row_to_signal(row) for row in rows]
        return signals, total
```

---

### 任务 3：创建 PositionService（应用层）

**文件**: `application/position_service.py`（新建）

**需求**:
封装持仓查询和钱包余额查询业务逻辑

**参考实现**:
```python
"""
应用层：持仓查询服务
职责：编排账户读取器和仓储，提供持仓相关用例
"""
from core.interfaces import IAccountReader, IRepository

class PositionService:
    """持仓应用服务"""

    def __init__(self, account_reader: IAccountReader, repo: IRepository):
        self.account_reader = account_reader
        self.repo = repo

    async def refresh_positions(self) -> List[dict]:
        """
        实时刷新持仓
        从币安 API 获取最新持仓数据
        """
        # 调用账户读取器获取实时持仓
        positions = await self.account_reader.fetch_positions()
        return positions

    async def get_wallet_balance(self) -> float:
        """
        获取钱包余额（初始保证金）
        """
        account = await self.account_reader.fetch_account_balance()
        return account.wallet_balance

    async def get_unrealized_pnl(self) -> float:
        """
        获取总计未实现盈亏
        """
        account = await self.account_reader.fetch_account_balance()
        return account.unrealized_pnl

    async def get_margin_balance(self, wallet_balance: float, unrealized_pnl: float) -> float:
        """
        计算保证金余额 = 钱包余额 + 未实现盈亏
        """
        return wallet_balance + unrealized_pnl
```

---

### 任务 4：改造 /api/signals 接口

**文件**: `web/api.py`

**需求**:
使用新的 SignalQueryService，返回分页格式

**参考实现**:
```python
@app.get("/api/signals")
async def get_signals(
    request: Request,
    symbols: Optional[str] = None,
    intervals: Optional[str] = None,
    directions: Optional[str] = None,
    start_time: Optional[int] = None,
    end_time: Optional[int] = None,
    min_score: Optional[int] = None,
    quality_tier: Optional[str] = None,
    page: Optional[int] = 1,
    size: Optional[int] = 20,
    sort_by: Optional[str] = "timestamp",
    order: Optional[str] = "desc"
):
    """
    分页查询信号列表
    """
    # 解析逗号分隔的参数
    symbols_list = symbols.split(",") if symbols else None
    intervals_list = intervals.split(",") if intervals else None
    directions_list = directions.split(",") if directions else None

    # 获取服务（从 app.state 或新建）
    service = request.app.state.signal_query_service
    if not service:
        from application.signal_query_service import SignalQueryService
        from infrastructure.repo.sqlite_repo import SQLiteRepo
        repo = SQLiteRepo()
        service = SignalQueryService(repo)

    # 执行查询
    result = await service.query_signals(
        symbols=symbols_list,
        intervals=intervals_list,
        directions=directions_list,
        start_time=start_time,
        end_time=end_time,
        min_score=min_score,
        quality_tier=quality_tier,
        page=page,
        size=size,
        sort_by=sort_by,
        order=order
    )

    # 转换为字典
    def signal_to_dict(s: Signal) -> dict:
        return {
            "id": s.id,
            "symbol": s.symbol,
            "interval": s.interval,
            "direction": s.direction,
            "entry_price": s.entry_price,
            "stop_loss": s.stop_loss,
            "take_profit_1": s.take_profit_1,
            "timestamp": s.timestamp,
            "score": s.score,
            "quality_tier": s.quality_tier,
            "shadow_ratio": s.shadow_ratio,
            "ema_distance": s.ema_distance,
            "volatility_atr": s.volatility_atr,
        }

    return {
        "items": [signal_to_dict(s) for s in result.items],
        "total": result.total,
        "page": result.page,
        "size": result.size
    }
```

**注意**: 确保默认值生效 - 当所有条件都未设置时，使用默认查询（page=1, size=20）

---

### 任务 5：新增 /api/positions/refresh 接口

**文件**: `web/api.py`

**参考实现**:
```python
@app.get("/api/positions/refresh")
async def refresh_positions(request: Request):
    """
    实时刷新持仓
    从币安 API 获取最新持仓数据
    """
    service = request.app.state.position_service
    if not service:
        from application.position_service import PositionService
        from infrastructure.repo.sqlite_repo import SQLiteRepo
        from infrastructure.feed.binance_api_reader import BinanceAccountReader

        repo = SQLiteRepo()
        account_reader = BinanceAccountReader(repo)  # 需要确保有实现
        service = PositionService(account_reader, repo)

    positions = await service.refresh_positions()
    return {"positions": positions}
```

---

### 任务 6：新增 /api/account/wallet-balance 接口

**文件**: `web/api.py`

**参考实现**:
```python
@app.get("/api/account/wallet-balance")
async def get_wallet_balance(request: Request):
    """
    获取钱包余额（初始保证金）
    """
    service = request.app.state.position_service
    if not service:
        # 同上，初始化服务
        pass

    balance = await service.get_wallet_balance()
    return {"wallet_balance": balance}
```

---

### 任务 7：改造 /api/account/dashboard 接口

**文件**: `web/api.py`

**需求**:
返回新字段结构

**旧返回**:
```json
{
  "total_wallet_balance": 10000,
  "available_balance": 8000,
  "total_unrealized_pnl": 500
}
```

**新返回**:
```json
{
  "wallet_balance": 10000,
  "total_unrealized_pnl": 500,
  "margin_balance": 10500,
  "current_positions_count": 3,
  "positions": []
}
```

**参考实现**:
```python
@app.get("/api/account/dashboard")
async def get_account_dashboard(request: Request):
    """
    账户仪表盘数据
    """
    service = request.app.state.position_service
    if not service:
        # 初始化服务
        pass

    # 获取数据
    wallet_balance = await service.get_wallet_balance()
    unrealized_pnl = await service.get_unrealized_pnl()
    margin_balance = await service.get_margin_balance(wallet_balance, unrealized_pnl)
    positions = await service.refresh_positions()

    return {
        "wallet_balance": wallet_balance,
        "total_unrealized_pnl": unrealized_pnl,
        "margin_balance": margin_balance,
        "current_positions_count": len(positions),
        "positions": positions
    }
```

---

### 任务 8：服务注册（依赖注入）

**文件**: `main.py`

**需求**:
在应用启动时注册服务到 app.state

**参考实现**:
```python
@app.on_event("startup")
async def startup_event():
    # ... 现有初始化代码 ...

    # 注册信号查询服务
    from application.signal_query_service import SignalQueryService
    app.state.signal_query_service = SignalQueryService(repo)

    # 注册持仓服务
    from application.position_service import PositionService
    from infrastructure.feed.binance_api_reader import BinanceAccountReader
    account_reader = BinanceAccountReader(repo)
    app.state.position_service = PositionService(account_reader, repo)
```

---

## 开发规范

### DDD 原则
1. **领域层纯净**：domain/ 下不允许有 async/await、I/O 操作
2. **应用层编排**：application/ 负责协调 domain 和 infrastructure
3. **仓储抽象**：应用层依赖 core/interfaces.py 中的抽象接口
4. **实体行为**：业务逻辑优先放在领域层，而非实体中

### 代码风格
- 类型注解完整
- 文档字符串清晰
- 异常处理明确

### 错误处理
```python
from fastapi import HTTPException

try:
    result = await service.query_signals(...)
except Exception as e:
    logger.error(f"查询失败：{e}")
    raise HTTPException(status_code=500, detail="查询服务异常")
```

---

## 验收标准

### 功能验收
- [ ] `/api/signals` 返回分页格式（items, total, page, size）
- [ ] 默认查询条件生效（page=1, size=20）
- [ ] 筛选条件正确过滤
- [ ] 排序功能正常
- [ ] `/api/positions/refresh` 返回实时持仓
- [ ] `/api/account/dashboard` 返回新字段结构

### 代码质量
- [ ] DDD 分层清晰
- [ ] 应用层不直接访问数据库，通过仓储接口
- [ ] 领域层无 I/O 操作
- [ ] 类型注解完整
- [ ] 无 Pyright 错误

### 性能
- [ ] 分页查询有数据库索引优化
- [ ] 大表查询有性能测试

---

## 完成后

1. 运行 `python -m pyright` 检查类型
2. 准备与前端联调
3. 使用 Postman 或 curl 测试所有新接口
