import sys
sys.path.append('.')
from web.api import ConfigUpdateReq

try:
    ConfigUpdateReq.model_rebuild()
    req = ConfigUpdateReq.model_validate({"monitor_intervals": {"15m": {"use_trend_filter": False}}})
    print(req)
except Exception as e:
    import traceback
    traceback.print_exc()
