# 新 fork 的视觉兼容改造

维护仓库为 `sinfee/PolyStrata`，基线为 VecSzn 上游提交 `ceb55be494378607ea756b173af7954dbfc8bdda`。
旧 `sinfee/PolyStrata-Fork` 仅作为 GLM 视觉补丁的参考，不再作为后续更新来源。

## 2026-10-20 上游同步

已合入 VecSzn `v0.1.45-poly.2`（`974552f5`）。该标签没有修改 GLM 与 DeepSeek 的模型类，
两者仍继承默认返回 false 的 `Engine::sees()`，服务层也尚未包含本地图片标记和 DeepSeek 位置对齐。
因此仍须保留这些兼容补丁，不能仅凭包内有视觉编码器改用未修改的上游程序。

本次新增 `STRATA_FATTN` / `STRATA_FDEC` 只接入 Qwen3.6 注意力路径，不适用于 GLM 或 DeepSeek，
也不用于工作区独立部署的 Qwen3.8 local-high。`--skip-weight` 与 `--stage-read-mib` 位于共享引擎，
DeepSeek 可以进入相应路径，但上游只提供 GLM 的收益数据，尚不能宣称 DeepSeek 已提速。
这两项默认关闭；前者跳过低路由权重的主存专家，会改变模型计算，后者为提示词读取临时借用专家缓存显存。
`--stage-read-mib` 不替代本地使用主存的 `--read-buffer-mib`。

本轮只同步源码与运行无 GPU 回归，不编译或替换生产运行时；真实图片与性能留待编译后验证。

## 改造范围

- GLM 开启通用图片嵌入输入能力，保留 `<|begin_of_image|>` 与 `<|image|>` 标记。
- DeepSeek-V4 的视觉实验权重使用 `<｜deepseek_image｜>` 标记和相同的图片嵌入输入协议；仍须针对实际 Vision-Exp 权重验证，不能将文字版权重视为视觉模型。
- DeepSeek 图片块按原生四 token 边界调整前导 pad；独立编码器的原始缓存保持不变。当前 Vision-Exp 使用原生 384 图像 token 上限，不能套用 Qwen 的 1024–4096 范围。
- OpenAI Chat、Responses、Anthropic 与 token 计数路径区分 GLM/DeepSeek 的 high/max；配置中的默认档位也保留原值，避免经 Qwen 的 xhigh 映射改变语义。
- 保留 `--read-buffer-mib`，默认仍为 512 MiB，可按主存条件调整；它改变长输入读取分段，不改模型权重或采样。
- Windows 调试信息使用 `/Z7`，避免并行编译共写 PDB；不改变模型算法。
- Qwen3.8 的主引擎继续使用对应 Niko1221/Strata 官方发布程序。三个程序可以由一份运行时清单管理，不要求每次都重编译所有引擎。

`strata-vision` 只负责编码图片；主引擎还必须支持接收图片嵌入。因此包内存在该 EXE 并不能证明每个模型分支都已支持视觉。

## 构建与更新

未有项目显式工具链要求时，优先本机最新 Visual Studio 及对应工具集；本次验证使用 VS2026 Community/v145（MSVC 14.51）、CUDA 13.4、sm_120。
有明确指定的项目平台不自动重定向。CUDA 不支持当前编译器时，才选择受支持的工具集并记录原因。

依赖遵守 `third_party/ggml/VERSION.txt` 的精确提交，禁止用本机其他 llama.cpp HEAD 静默替代。
本机验证版和公开可移植发布版应分别标明 CUDA、MSVC、CPU 指令集与 GPU 架构，不能混称同一构建。

`tools/make_poly_release.py` 沿用上游的可移植发布构建约束。
`tools/pack_runtime_release.py` 则将已经验证的主引擎和同源码指纹的视觉程序打包，校验构建清单和干净源码提交，不重新编译。
非可移植的本机构建包会显式写入 `portable: false`，只用于符合记录硬件要求的机器。

工作区更新器使用已提交的本地兼容源码，候选检出合入上游最新正式标签，再本机编译与进行真实文字和视觉试加载。
无需发布 fork；来源、依赖、构建指纹与回退备份须保留。合并或验证失败保留原生产运行时。

## 验证

```text
python -m unittest serve.test_vision_effort_compat
python -m unittest serve.test_server tools.test_poly_prebuilt
```

这些模拟服务测试不能替代真实图片、长输入、工具安全和吞吐测试。能力、速度和视觉验证必须记录具体权重、KV、思考档位、输入长度与运行时指纹。
