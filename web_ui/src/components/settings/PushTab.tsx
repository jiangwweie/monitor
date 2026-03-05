import { useState, useEffect } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Eye, EyeOff, Loader2 } from "lucide-react";
import { toast } from "sonner";

interface PushTabProps {
  initialConfig: any;
  onConfigChange: (field: string, value: any) => void;
}

export function PushTab({ initialConfig, onConfigChange }: PushTabProps) {
  const [loading, setLoading] = useState(false);
  const [showSecret, setShowSecret] = useState(false);
  const [showWecomSecret, setShowWecomSecret] = useState(false);

  const [formData, setFormData] = useState({
    global_push_enabled: true,
    feishu_enabled: false,
    feishu_secret: "",
    has_secret: false,
    wecom_enabled: false,
    wecom_secret: "",
    has_wecom_secret: false,
  });

  useEffect(() => {
    setFormData({
      global_push_enabled: initialConfig.global_push_enabled ?? true,
      feishu_enabled: initialConfig.feishu_enabled ?? false,
      feishu_secret: initialConfig.feishu_secret || "",
      has_secret: initialConfig.has_secret ?? false,
      wecom_enabled: initialConfig.wecom_enabled ?? false,
      wecom_secret: initialConfig.wecom_secret || "",
      has_wecom_secret: initialConfig.has_wecom_secret ?? false,
    });
  }, [initialConfig]);

  const handleSave = async () => {
    setLoading(true);
    try {
      const payload: any = {
        global_push_enabled: Boolean(formData.global_push_enabled),
        feishu_enabled: Boolean(formData.feishu_enabled),
        wecom_enabled: Boolean(formData.wecom_enabled),
      };

      if (formData.feishu_secret) {
        payload.feishu_secret = formData.feishu_secret;
      }
      if (formData.wecom_secret) {
        payload.wecom_secret = formData.wecom_secret;
      }

      const res = await fetch("http://localhost:8000/api/config/push", {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        toast.success("推送配置已保存", {
          description: "飞书和企微推送设置已更新。",
          className: "bg-zinc-900 border border-white/10 text-zinc-100",
        });
        onConfigChange("global_push_enabled", formData.global_push_enabled);
        onConfigChange("feishu_enabled", formData.feishu_enabled);
        onConfigChange("wecom_enabled", formData.wecom_enabled);
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
          <CardTitle className="text-zinc-900 dark:text-white">推送配置</CardTitle>
          <CardDescription>配置飞书和企业微信消息推送</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="flex items-center justify-between pb-4 border-b border-zinc-200 dark:border-white/10">
            <div>
              <Label className="text-base text-zinc-900 dark:text-zinc-200">
                全局推送开关
              </Label>
              <p className="text-xs text-zinc-500 mt-1">
                关闭后所有推送通道将停止工作
              </p>
            </div>
            <Switch
              checked={formData.global_push_enabled}
              onCheckedChange={(c) =>
                setFormData((prev) => ({ ...prev, global_push_enabled: c }))
              }
            />
          </div>

          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <Label className="text-zinc-900 dark:text-zinc-300">
                飞书机器人推送
              </Label>
              <Switch
                checked={formData.feishu_enabled}
                onCheckedChange={(c) =>
                  setFormData((prev) => ({ ...prev, feishu_enabled: c }))
                }
              />
            </div>
            <div className="relative">
              <Input
                type={showSecret ? "text" : "password"}
                value={formData.feishu_secret}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, feishu_secret: e.target.value }))
                }
                className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 pr-10 text-zinc-900 dark:text-white"
                placeholder={
                  formData.has_secret
                    ? "•••••••••••••••• (已保存)"
                    : "输入飞书 Webhook 密钥..."
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

          <div className="space-y-4 pt-4 border-t border-zinc-200 dark:border-white/10">
            <div className="flex items-center justify-between">
              <Label className="text-zinc-900 dark:text-zinc-300">
                企业微信推送
              </Label>
              <Switch
                checked={formData.wecom_enabled}
                onCheckedChange={(c) =>
                  setFormData((prev) => ({ ...prev, wecom_enabled: c }))
                }
              />
            </div>
            <div className="relative">
              <Input
                type={showWecomSecret ? "text" : "password"}
                value={formData.wecom_secret}
                onChange={(e) =>
                  setFormData((prev) => ({ ...prev, wecom_secret: e.target.value }))
                }
                className="bg-white dark:bg-black/20 border-zinc-200 dark:border-white/10 pr-10 text-zinc-900 dark:text-white"
                placeholder={
                  formData.has_wecom_secret
                    ? "•••••••••••••••• (已保存)"
                    : "输入企微 Webhook 密钥..."
                }
              />
              <button
                type="button"
                onClick={() => setShowWecomSecret(!showWecomSecret)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-zinc-500 hover:text-zinc-300"
              >
                {showWecomSecret ? (
                  <EyeOff className="w-4 h-4" />
                ) : (
                  <Eye className="w-4 h-4" />
                )}
              </button>
            </div>
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
              "保存推送配置"
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}
