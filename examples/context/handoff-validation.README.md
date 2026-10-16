# Context Pack 校验示例

在项目根目录执行：

```powershell
aimes context pack examples/traceability/trace-manifest.example.yaml --output-dir .aimes/context-pack
aimes context validate .aimes/context-pack/context-pack.json --handoff .aimes/context-pack/HANDOFF.md
```

如果 Context Pack 生成后，所引用的任意源文件发生变化，校验将报告 `CONTEXT_HASH_CHANGED`。这用于提示接手者重新审阅，不自动判断变化是否合理。
