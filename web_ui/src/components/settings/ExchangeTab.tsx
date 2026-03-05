import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Database, Eye, EyeOff, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface ExchangeTabProps {
  initialConfig: any;
}

export function ExchangeTab({ initialConfig }: ExchangeTabProps) {
  const [loading, setLoading] = useState(false);
  const [showSecret, setShowSecret] = useState(false);

  const [formData, setFormData] = useState({
    binance_api_key: "",
    binance_api_secret: "",
    has_binance_key: false,
  });

  useEffect(() => {
    setFormData({
      binance_api_key: initialConfig.binance_api_key || "",
      binance_api_secret: initialConfig.binance_api_secret || "",
      has_binance_key: initialConfig.has_binance_key || false,
    });
  }, [initialConfig]);

  const handleSave = async () => {
    setLoading(true);
    try {
      const payload: any = {};

      if (formData.binance_api_key) {
        payload.binance_api_key = formData.binance_api_key;
      }
      if (formData.binance_api_secret) {
        payload.binance_api_secret = formData.binance_api_secret;
      }

      const res = await fetch("http://localhost:8000/api/config/exchange", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        toast.success("交易所配置已保存", {
          description: "API 密钥已更新。",
          className: "bg-zinc-900 border border-white/10 text-zinc-100",
        });
      } else {
        throw new Error("Save failed");
      }
    } catch (error) {
      toast.error("保存失败", {
        description: "后端服务离线或网络异常。",
        className: "bg-red-950 border border-red-900",
      });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-zinc-900 dark:text-white">
            <Database className="w-5 h-5" /> 交易所配置
          </CardTitle>
          <CardDescription>配置币安 API 密钥</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label className="text-zinc-700 dark:text-zinc-300">
                币安 API Key (仅供读取)
              </Label>
              <Input
                value={formData.binance_api_key}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, binance_api_key: e.target.value }))
                }
                className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 text-zinc-900 dark:text-white placeholder:text-zinc-400 font-mono"
                placeholder={
                  formData.has_binance_key
                    ? "******** (目前密钥已配置成功)"
                    : "输入币安 API Key"
                }
              />
            </div>

            <div className="space-y-2">
              <Label className="text-zinc-700 dark:text-zinc-300">
                币安 API Secret
              </Label>
              <div className="relative">
                <Input
                  type={showSecret ? "text" : "password"}
                  value={formData.binance_api_secret}
                  onChange={(e) =>
                    setFormData((prev) => ({ ...prev, binance_api_secret: e.target.value }))
                  }
                  className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 pr-10 text-zinc-900 dark:text-white placeholder:text-zinc-400 font-mono"
                  placeholder={
                    formData.has_binance_key
                      ? "******** (加密隐藏)"
                      : "输入币安 API Secret"
                  }
                />
                <button
                  type="button"
                  onClick={() => setShowSecret(!showSecret)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
                >
                  {showSecret ? (
                    <EyeOff className="w-4 h-4" />
                  ) : (
                    <Eye className="w-4 h-4" />
                  )}
                </button>
              </div>
            </div>
            <p className="text-xs text-zinc-500 mt-2">
              安全提示：密钥将在后台强制加密存储，请确保该秘钥仅开启只读权限，严禁开启交易与提现权限。
            </p>
          </div>

          <Button
            onClick={handleSave}
            disabled={loading}
            className="w-full h-12 rounded-2xl bg-zinc-900 text-white dark:bg-white dark:text-black hover:bg-zinc-800 dark:hover:bg-zinc-200 transition-all text-base font-semibold shadow-xl shadow-black/5 dark:shadow-white/5"
          >
            {loading ? (
              <>
                <Loader2 className="w-5 h-5 animate-spin mr-2" /> 保存中...
              </>
            ) : (
              "保存交易所配置"
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
