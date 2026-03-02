"""
 基础设施层：SQLite 异步只读/写仓储
 实现 IRepository 接口用于记录交易信号及风控算仓快照，
 包含按条件查询信号、删除、清理、和简单加解密安全落盘等高级功能。
"""
import logging
import asyncio
import json
import time
from typing import List, Tuple

import aiosqlite

from core.entities import Signal, PositionSizing, SignalFilter
from core.interfaces import IRepository
from infrastructure.utils.encryptor import simple_encrypt, simple_decrypt

logger = logging.getLogger(__name__)

class SQLiteRepo(IRepository):
    """
    基于 aiosqlite 的持久化仓储（完整版）。
    支持完整的分页、聚合、筛选、安全加解密和数据清理运维。
    """
    def __init__(self, db_path: str = "radar.db"):
        self.db_path = db_path
        
    async def init_db(self):
        """建库建表语句"""
        async with aiosqlite.connect(self.db_path) as db:
            # 启用 WAL 模式：允许并发读写，防止历史扫描与实时监控写入冲突
            await db.execute("PRAGMA journal_mode=WAL")
            # 遇到锁时等待 5 秒而非立即报错
            await db.execute("PRAGMA busy_timeout=5000")
            await db.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    symbol TEXT,
                    direction TEXT,
                    entry_price REAL,
                    stop_loss REAL,
                    take_profit_1 REAL,
                    timestamp INTEGER,
                    reason TEXT,
                    sl_distance_pct REAL,
                    score INTEGER,
                    score_details TEXT,
                    shadow_ratio REAL,
                    ema_distance REAL,
                    volatility_atr REAL,
                    created_at INTEGER
                )
            ''')
            
            await db.execute('''
                CREATE TABLE IF NOT EXISTS position_sizings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    signal_timestamp INTEGER,
                    suggested_leverage REAL,
                    suggested_quantity REAL,
                    investment_amount REAL,
                    risk_amount REAL,
                    created_at INTEGER
                )
            ''')
            
            # 用于保存配置例如 Secret 等等
            await db.execute('''
                CREATE TABLE IF NOT EXISTS configs (
                    config_key TEXT PRIMARY KEY,
                    config_value TEXT
                )
            ''')
            
            # 尝试为旧表添加新字段 (如果表已存在)
            try:
                await db.execute("ALTER TABLE signals ADD COLUMN shadow_ratio REAL DEFAULT 0.0")
            except aiosqlite.OperationalError: pass
            
            try:
                await db.execute("ALTER TABLE signals ADD COLUMN ema_distance REAL DEFAULT 0.0")
            except aiosqlite.OperationalError: pass
            
            try:
                await db.execute("ALTER TABLE signals ADD COLUMN volatility_atr REAL DEFAULT 0.0")
            except aiosqlite.OperationalError: pass
            
            try:
                await db.execute("ALTER TABLE signals ADD COLUMN interval TEXT DEFAULT '1h'")
            except aiosqlite.OperationalError: pass

            try:
                await db.execute("ALTER TABLE signals ADD COLUMN source TEXT DEFAULT 'realtime'")
            except aiosqlite.OperationalError: pass

            try:
                await db.execute("ALTER TABLE signals ADD COLUMN is_shape_divergent BOOLEAN DEFAULT 0")
            except aiosqlite.OperationalError: pass

            await db.commit()
            
    # ======== IRepository 实现 ========

    async def save_signal(self, signal: Signal) -> None:
        """异步持久化验证成功的信号"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO signals (
                    symbol, interval, direction, entry_price, stop_loss, take_profit_1,
                    timestamp, reason, sl_distance_pct, score, score_details,
                    shadow_ratio, ema_distance, volatility_atr, source, is_shape_divergent, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                signal.symbol,
                signal.interval,
                signal.direction,
                signal.entry_price,
                signal.stop_loss,
                signal.take_profit_1,
                signal.timestamp,
                signal.reason,
                signal.sl_distance_pct,
                signal.score,
                json.dumps(signal.score_details),
                signal.shadow_ratio,
                signal.ema_distance,
                signal.volatility_atr,
                signal.source,
                signal.is_shape_divergent,
                int(time.time() * 1000)
            ))
            await db.commit()
            logger.info(f"[DB] 信号入库成功: {signal.symbol} {signal.interval} {signal.direction} 得分={signal.score}")

    async def save_position_sizing(self, sizing: PositionSizing) -> None:
        """异步持久化算仓推荐快照"""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT INTO position_sizings (
                    signal_timestamp, suggested_leverage, suggested_quantity, 
                    investment_amount, risk_amount, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
            ''', (
                sizing.signal.timestamp,
                sizing.suggested_leverage,
                sizing.suggested_quantity,
                sizing.investment_amount,
                sizing.risk_amount,
                int(time.time() * 1000)
            ))
            await db.commit()
            
    async def get_signals(self, filter_params: SignalFilter, page: int = 1, size: int = 50) -> Tuple[int, List[dict]]:
        """按过滤条件分页查询历史信号。此处直接返回字典以便 FastAPI 序列化 JSON"""
        query = "SELECT * FROM signals WHERE 1=1"
        params = []
        
        if filter_params.symbols:
            placeholders = ','.join('?' * len(filter_params.symbols))
            query += f" AND symbol IN ({placeholders})"
            params.extend(filter_params.symbols)
            
        if filter_params.intervals:
            placeholders = ','.join('?' * len(filter_params.intervals))
            query += f" AND interval IN ({placeholders})"
            params.extend(filter_params.intervals)
            
        if filter_params.directions:
            placeholders = ','.join('?' * len(filter_params.directions))
            query += f" AND direction IN ({placeholders})"
            params.extend(filter_params.directions)
            
        if filter_params.start_time:
            query += " AND timestamp >= ?"
            params.append(filter_params.start_time)
            
        if filter_params.end_time:
            query += " AND timestamp <= ?"
            params.append(filter_params.end_time)
            
        if filter_params.min_score is not None:
            query += " AND score >= ?"
            params.append(filter_params.min_score)
            
        count_query = query.replace("SELECT *", "SELECT COUNT(1)")
        
        sort_field = "score" if filter_params.sort_by == "score" else "timestamp"
        sort_order = "ASC" if filter_params.order and filter_params.order.lower() == "asc" else "DESC"
        query += f" ORDER BY {sort_field} {sort_order} LIMIT ? OFFSET ?"
        
        offset = (page - 1) * size
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(count_query, params)
            total = (await cursor.fetchone())[0]
            
            params.extend([size, offset])
            cursor = await db.execute(query, params)
            rows = await cursor.fetchall()
            
            items = []
            for row in rows:
                item = dict(row)
                if isinstance(item.get('score_details'), str):
                    try:
                        item['score_details'] = json.loads(item['score_details'])
                    except:
                        item['score_details'] = {}
                items.append(item)
                
            return total, items

    async def delete_signals(self, ids: List[int]) -> int:
        """根据内部ID列表批量删除信号，返回删除成功条数"""
        if not ids:
            return 0
        async with aiosqlite.connect(self.db_path) as db:
            placeholders = ','.join('?' * len(ids))
            cursor = await db.execute(f"DELETE FROM signals WHERE id IN ({placeholders})", ids)
            await db.commit()
            return cursor.rowcount

    async def cleanup_old_signals(self, days: int = 7) -> int:
        """一键清理 N 天前数据记录"""
        limit_time = int((time.time() - days * 86400) * 1000)
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(f"DELETE FROM signals WHERE timestamp < ?", (limit_time,))
            await db.commit()
            return cursor.rowcount

    # ======== 安全配置存取 ========
    
    async def set_secret(self, key: str, plain_secret: str) -> None:
        """以密文形式存储安全凭据"""
        encrypted_val = simple_encrypt(plain_secret)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                INSERT OR REPLACE INTO configs (config_key, config_value)
                VALUES (?, ?)
            ''', (key, encrypted_val))
            await db.commit()
            
    async def get_secret(self, key: str) -> str:
        """读取并解密安全凭据"""
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute('SELECT config_value FROM configs WHERE config_key = ?', (key,))
            row = await cursor.fetchone()
            if row:
                return simple_decrypt(row[0])
            return ""
