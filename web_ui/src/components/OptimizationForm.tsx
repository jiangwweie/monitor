/**
 * Optimization Form
 * 参数网格优化配置表单
 */

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Slider } from "@/components/ui/slider";
import { Plus, X, Zap } from "lucide-react";

import type { BacktestConfig } from "@/services/backtest_api";

export interface OptimizationParamItem {
  name: string;
  valuesStr: string;    // 用户输入的逗号分隔字符串
}

export interface OptimizationRequest {
  base_config: Record<string, any>;
  params: Array<{ name: string; values: any[] }>;
  objective: string;
  top_n: number;
  max_combinations: number;
}

interface OptimizationFormProps {
  baseConfig: BacktestConfig;
  onSubmit: (config: OptimizationRequest) => void;
}

// 默认参数配置
const DEFAULT_PARAMS: OptimizationParamItem[] = [
  { name: "ema_period", valuesStr: "30, 60, 90, 120" },
  { name: "leverage", valuesStr: "5, 10, 20" },
  { name: "risk_pct", valuesStr: "0.01, 0.02, 0.03" },
];

// 组合数提示组件
function CombinationsHint({ params }: { params: OptimizationParamItem[] }) {
  const validParams = params.filter((p) => p.name && p.valuesStr);
  const parsedParams = validParams.map((p) => ({
    name: p.name,
    values: p.valuesStr
      .split(",")
      .map((v) => v.trim())
      .filter((v) => v !== "")
      .map((v) => {
        const num = Number(v);
        return isNaN(num) ? v : num;
      }),
  }));

  const totalCombinations = parsedParams.reduce((acc, p) => acc * p.values.length, 1);
  const actualCombinations = Math.min(totalCombinations, 200);

  if (validParams.length === 0 || totalCombinations === 0) {
    return null;
  }

  return (
    <p className="text-xs text-zinc-500">
      预计执行 <span className="font-mono text-yellow-500">{actualCombinations}</span> 次回测
      {totalCombinations > 200 && (
        <span className="text-orange-400">（已截断，原始 {totalCombinations} 个组合）</span>
      )}
    </p>
  );
}

const OBJECTIVE_OPTIONS = [
  { value: "total_return_pct", label: "总收益率" },
  { value: "sharpe_ratio", label: "夏普比率" },
  { value: "win_rate", label: "胜率" },
  { value: "profit_factor", label: "盈亏比" },
];

export function OptimizationForm({
  baseConfig,
  onSubmit,
}: OptimizationFormProps) {
  const [params, setParams] = useState<OptimizationParamItem[]>(DEFAULT_PARAMS);
  const [objective, setObjective] = useState("total_return_pct");
  const [topN, setTopN] = useState(10);

  const handleAddParam = () => {
    setParams([...params, { name: "", valuesStr: "" }]);
  };

  const handleRemoveParam = (index: number) => {
    setParams(params.filter((_, i) => i !== index));
  };

  const handleParamChange = (index: number, field: keyof OptimizationParamItem, value: string) => {
    const newParams = [...params];
    newParams[index] = { ...newParams[index], [field]: value };
    setParams(newParams);
  };

  const parseValues = (valuesStr: string): any[] => {
    return valuesStr
      .split(",")
      .map((v) => v.trim())
      .filter((v) => v !== "")
      .map((v) => {
        const num = Number(v);
        return isNaN(num) ? v : num;
      });
  };

  const handleSubmit = () => {
    // 验证参数
    const validParams = params.filter((p) => p.name && p.valuesStr);
    if (validParams.length === 0) {
      alert("请至少添加一个参数");
      return;
    }

    const parsedParams = validParams.map((p) => ({
      name: p.name,
      values: parseValues(p.valuesStr),
    }));

    const request: OptimizationRequest = {
      base_config: baseConfig as Record<string, any>,
      params: parsedParams,
      objective,
      top_n: topN,
      max_combinations: 200,    // 固定安全上限，不使用 totalCombinations
    };

    onSubmit(request);
  };

  return (
    <Card className="backdrop-blur-xl bg-white/5 border border-zinc-200 dark:border-white/10 rounded-3xl overflow-hidden">
      <CardHeader className="pb-4 border-b border-zinc-200 dark:border-white/5">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-yellow-500" />
          <CardTitle className="text-zinc-900 dark:text-zinc-200">
            参数网格优化
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="p-6 space-y-6">
        {/* 参数列表 */}
        <div className="space-y-3">
          <Label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            优化参数
          </Label>

          {params.map((param, index) => (
            <div key={index} className="flex items-center gap-3">
              <Input
                placeholder="参数名 (如 ema_period)"
                value={param.name}
                onChange={(e) => handleParamChange(index, "name", e.target.value)}
                className="w-48 font-mono text-sm"
              />
              <span className="text-zinc-500">:</span>
              <Input
                placeholder="候选值，逗号分隔 (如 30, 60, 90)"
                value={param.valuesStr}
                onChange={(e) => handleParamChange(index, "valuesStr", e.target.value)}
                className="flex-1 font-mono text-sm"
              />
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleRemoveParam(index)}
                className="h-9 w-9 p-0 text-zinc-500 hover:text-red-500"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          ))}

          <Button
            variant="outline"
            size="sm"
            onClick={handleAddParam}
            className="mt-2"
          >
            <Plus className="w-4 h-4 mr-2" />
            添加参数
          </Button>
        </div>

        {/* 优化目标 */}
        <div className="space-y-2">
          <Label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
            优化目标
          </Label>
          <Select value={objective} onValueChange={setObjective}>
            <SelectTrigger className="w-full max-w-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {OBJECTIVE_OPTIONS.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Top-N 数量 */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
              显示 Top-N 结果
            </Label>
            <span className="text-sm font-mono text-zinc-500">{topN}</span>
          </div>
          <Slider
            value={[topN]}
            onValueChange={(v) => setTopN(v[0])}
            min={1}
            max={50}
            step={1}
            className="max-w-xs"
          />
        </div>

        {/* 组合数提示 */}
        <CombinationsHint params={params} />

        {/* 提交按钮 */}
        <Button
          onClick={handleSubmit}
          className="w-full bg-yellow-500 hover:bg-yellow-600 text-white"
        >
          <Zap className="w-4 h-4 mr-2" />
          开始优化
        </Button>
      </CardContent>
    </Card>
  );
}
