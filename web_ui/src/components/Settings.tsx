import { useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Clock, Zap, ShieldCheck, Download } from "lucide-react";

import {
  MonitorTab,
  PinbarTab,
  RiskTab,
  ImportExportTab,
} from "./settings/index";

interface SettingsProps {
  config: {
    symbols: string;
    monitor_intervals: string[];
    body_max_ratio: number;
    shadow_min_ratio: number;
    volatility_atr_multiplier: number;
    doji_threshold: number;
    doji_shadow_bonus: number;
    mtf_trend_filter_mode: string;
    dynamic_sl_enabled: boolean;
    dynamic_sl_base: number;
    dynamic_sl_atr_multiplier: number;
    risk_pct: number;
    max_sl_dist: number;
    max_leverage: number;
    max_position_value_ratio: number;
    w_shape: number;
    w_trend: number;
    w_vol: number;
  };
  onConfigChange: (field: string, value: unknown) => void;
}

export function Settings({ config, onConfigChange }: SettingsProps) {
  const [activeTab, setActiveTab] = useState("monitor");

  const tabs = [
    { id: "monitor", label: "监控", icon: Clock },
    { id: "pinbar", label: "Pinbar", icon: Zap },
    { id: "risk", label: "风控", icon: ShieldCheck },
    { id: "import", label: "导入导出", icon: Download },
  ];

  return (
    <div className="space-y-6">
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-white/50 dark:bg-white/5 border border-black/10 dark:border-white/10 rounded-2xl h-12 w-full justify-start p-1.5 mb-6 shadow-sm dark:shadow-none overflow-x-auto">
          {tabs.map((tab) => (
            <TabsTrigger
              key={tab.id}
              value={tab.id}
              className="rounded-xl px-4 data-[state=active]:bg-white dark:data-[state=active]:bg-zinc-800 data-[state=active]:text-zinc-900 dark:data-[state=active]:text-white data-[state=active]:shadow-sm dark:data-[state=active]:shadow-none transition-all whitespace-nowrap"
            >
              <tab.icon className="w-4 h-4 mr-2" />
              {tab.label}
            </TabsTrigger>
          ))}
        </TabsList>

        <TabsContent value="monitor">
          <MonitorTab
            initialConfig={config}
            onConfigChange={onConfigChange}
          />
        </TabsContent>

        <TabsContent value="pinbar">
          <PinbarTab
            initialConfig={config}
            onConfigChange={onConfigChange}
          />
        </TabsContent>

        <TabsContent value="risk">
          <RiskTab
            initialConfig={config}
            onConfigChange={onConfigChange}
          />
        </TabsContent>

        <TabsContent value="import">
          <ImportExportTab />
        </TabsContent>
      </Tabs>
    </div>
  );
}
