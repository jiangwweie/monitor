import { useState } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Upload, Download, Loader2, CheckCircle2, XCircle } from "lucide-react";
import { toast } from "sonner";

export function ImportExportTab() {
  const [exportLoading, setExportLoading] = useState(false);
  const [importLoading, setImportLoading] = useState(false);
  const [importResult, setImportResult] = useState<{
    success: boolean;
    message: string;
  } | null>(null);

  const handleExport = async () => {
    setExportLoading(true);
    try {
      const res = await fetch("http://localhost:8000/api/config/export", {
        method: "POST",
      });

      if (res.ok) {
        const data = await res.json();
        toast.success("配置导出成功", {
          description: `文件已保存至：${data.file_path || "后端服务器目录"}`,
          className: "bg-zinc-900 border border-white/10 text-zinc-100",
        });
      } else {
        throw new Error("Export failed");
      }
    } catch (error) {
      toast.error("导出失败", {
        description: "后端服务离线或网络异常。",
        className: "bg-red-950 border border-red-900",
      });
    } finally {
      setExportLoading(false);
    }
  };

  const handleImport = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    if (!file.name.endsWith(".yaml") && !file.name.endsWith(".yml")) {
      toast.error("文件格式错误", {
        description: "请上传 YAML 格式的文件 (.yaml 或 .yml)",
        className: "bg-red-950 border border-red-900",
      });
      return;
    }

    setImportLoading(true);
    setImportResult(null);

    const reader = new FileReader();
    reader.onload = async (e) => {
      const yamlContent = e.target?.result as string;

      try {
        // 使用 FormData 发送
        const formData = new FormData();
        formData.append("yaml_content", yamlContent);

        const res = await fetch("http://localhost:8000/api/config/import", {
          method: "POST",
          body: formData,
          // 注意：不要手动设置 Content-Type，浏览器会自动设置 multipart/form-data
        });

        const data = await res.json();

        if (res.ok && data.status === "success") {
          setImportResult({ success: true, message: data.message || "配置导入成功" });
          toast.success("配置导入成功", {
            description: "页面将在 2 秒后刷新以应用新配置。",
            className: "bg-zinc-900 border border-white/10 text-zinc-100",
          });
          setTimeout(() => {
            window.location.reload();
          }, 2000);
        } else {
          setImportResult({
            success: false,
            message: data.detail || data.message || "导入失败，请检查文件格式",
          });
          toast.error("配置导入失败", {
            description: data.detail || data.message || "请检查文件格式",
            className: "bg-red-950 border border-red-900",
          });
        }
      } catch (error) {
        setImportResult({
          success: false,
          message: "网络错误或后端服务离线",
        });
        toast.error("导入失败", {
          description: "网络错误或后端服务离线。",
          className: "bg-red-950 border border-red-900",
        });
      } finally {
        setImportLoading(false);
      }
    };

    reader.onerror = () => {
      setImportLoading(false);
      toast.error("文件读取失败", {
        description: "无法读取文件内容。",
        className: "bg-red-950 border border-red-900",
      });
    };

    reader.readAsText(file);
    event.target.value = "";
  };

  return (
    <div className="space-y-6">
      <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl">
        <CardHeader>
          <CardTitle className="text-zinc-900 dark:text-white">配置导入导出</CardTitle>
          <CardDescription>备份和恢复系统配置</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Card className="backdrop-blur-xl bg-gradient-to-br from-blue-500/5 to-purple-500/5 border border-blue-500/20 rounded-2xl">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Download className="w-5 h-5 text-blue-500" />
                  导出配置
                </CardTitle>
                <CardDescription>
                  将当前所有配置导出为 YAML 文件
                </CardDescription>
              </CardHeader>
              <CardContent>
                <Button
                  onClick={handleExport}
                  disabled={exportLoading}
                  className="w-full h-12 rounded-2xl bg-blue-500 text-white hover:bg-blue-600 transition-all text-base font-semibold shadow-lg shadow-blue-500/20"
                >
                  {exportLoading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin mr-2" /> 导出中...
                    </>
                  ) : (
                    <>
                      <Download className="w-5 h-5 mr-2" />
                      导出配置
                    </>
                  )}
                </Button>
              </CardContent>
            </Card>

            <Card className="backdrop-blur-xl bg-gradient-to-br from-emerald-500/5 to-teal-500/5 border border-emerald-500/20 rounded-2xl">
              <CardHeader>
                <CardTitle className="text-lg flex items-center gap-2">
                  <Upload className="w-5 h-5 text-emerald-500" />
                  导入配置
                </CardTitle>
                <CardDescription>
                  从 YAML 文件恢复配置
                </CardDescription>
              </CardHeader>
              <CardContent>
                <label className="block">
                  <input
                    type="file"
                    accept=".yaml,.yml"
                    onChange={handleImport}
                    className="hidden"
                  />
                  <span className="flex items-center justify-center w-full h-12 rounded-2xl bg-emerald-500 text-white hover:bg-emerald-600 transition-all text-base font-semibold shadow-lg shadow-emerald-500/20 cursor-pointer">
                    {importLoading ? (
                      <>
                        <Loader2 className="w-5 h-5 animate-spin mr-2" /> 导入中...
                      </>
                    ) : (
                      <>
                        <Upload className="w-5 h-5 mr-2" />
                        选择文件导入
                      </>
                    )}
                  </span>
                </label>
              </CardContent>
            </Card>
          </div>

          {importResult && (
            <Card
              className={`rounded-2xl border ${
                importResult.success
                  ? "bg-emerald-500/10 border-emerald-500/30"
                  : "bg-red-500/10 border-red-500/30"
              }`}
            >
              <CardContent className="pt-6">
                <div className="flex items-center gap-3">
                  {importResult.success ? (
                    <CheckCircle2 className="w-6 h-6 text-emerald-500" />
                  ) : (
                    <XCircle className="w-6 h-6 text-red-500" />
                  )}
                  <p
                    className={`font-medium ${
                      importResult.success
                        ? "text-emerald-700 dark:text-emerald-400"
                        : "text-red-700 dark:text-red-400"
                    }`}
                  >
                    {importResult.message}
                  </p>
                </div>
              </CardContent>
            </Card>
          )}

          <Card className="backdrop-blur-xl bg-zinc-50 dark:bg-black/20 border border-zinc-200 dark:border-white/5 rounded-2xl">
            <CardContent className="pt-6">
              <h4 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100 mb-3">
                使用说明
              </h4>
              <ul className="space-y-2 text-sm text-zinc-600 dark:text-zinc-400">
                <li className="flex items-start gap-2">
                  <span className="text-blue-500 mt-1">•</span>
                  <span>导出功能会将当前所有配置（交易所、监控、策略、风控、推送）保存为 YAML 文件</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-500 mt-1">•</span>
                  <span>导入功能支持上传之前导出的 YAML 配置文件</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-500 mt-1">•</span>
                  <span>导入成功后页面将自动刷新以应用新配置</span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-blue-500 mt-1">•</span>
                  <span>配置文件包含敏感信息（如 API 密钥），请妥善保管</span>
                </li>
              </ul>
            </CardContent>
          </Card>
        </CardContent>
      </Card>
    </div>
  );
}
