import { Button } from "@/components/ui/button";
import { Save, RotateCcw } from "lucide-react";

interface ActionButtonsProps {
  onSave: () => void;
  onReset: () => void;
  hasUnsavedChanges: boolean;
  disabled?: boolean;
}

export function ActionButtons({
  onSave,
  onReset,
  hasUnsavedChanges,
  disabled,
}: ActionButtonsProps) {
  return (
    <div className="flex items-center gap-2">
      <Button
        variant="outline"
        size="sm"
        onClick={onReset}
        disabled={disabled}
        className="text-zinc-600 dark:text-zinc-400"
      >
        <RotateCcw className="w-4 h-4 mr-2" />
        重置
      </Button>
      <Button
        size="sm"
        onClick={onSave}
        disabled={disabled || !hasUnsavedChanges}
        className="bg-blue-600 hover:bg-blue-700 text-white"
      >
        <Save className="w-4 h-4 mr-2" />
        保存
        {hasUnsavedChanges && (
          <span className="ml-1 w-2 h-2 bg-white rounded-full animate-pulse" />
        )}
      </Button>
    </div>
  );
}
