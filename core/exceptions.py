"""
核心领域异常模块
定义系统中所有业务层面的自定义异常，用于业务流的短路和拦截。
"""

class RiskLimitExceeded(Exception):
    """
    风控超限异常
    当交易信号或账户状态超过安全风控阈值（如持仓已达上限、止损距离过大等）时抛出。
    此异常通常用于拦截发单流程，保护账户安全。
    """
    def __init__(self, message: str):
        super().__init__(message)
