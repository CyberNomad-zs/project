---
name: source-folders-are-variant-collections
description: 易之来灯具源文件夹是系列变体合集非单品，图源需型号核对
metadata: 
  node_type: memory
  type: project
  originSessionId: b88122c6-fc18-43c5-a7b3-3099a1cd10d8
---

关键发现（2026-07-07）：`文件/易之来灯具/<型号>/` 的源图文件夹**不是单个 SKU 的图**，而是**系列/变体合集**——一个文件夹混着同系列多个真实不同的型号。

例：`G125TBOA/` 文件夹里 8 张海报读出 5 个变体 `VS-G125TBOA/TSOA/HBOA/HSOA/MOA`（含一张全家福）；`ONE-DS120180MWAG/` 混着 RMC100162/GMC110160/BMC100162 等。

**Why 重要:** 直接 `pick_best_clean_shot` 盲选会选中错型号 → 货不对板，违背[[main-image-fidelity-decision]]的精确还原原则。B 阶段小批验收抓到了这个问题（详情海报型号与白底主图造型不符）。

**How to apply:** 上架前必须做图源型号核对。已建并验证 `src/match.py` 的 `resolve_source(sku,源目录)`：①OCR海报找该SKU单型号带标签海报作锚点(`ocr_model_codes`,grok-4.3) ②视觉配对`vision_compare`把无标签干净图绑到正确变体——**prompt必须聚焦判别性特征(如灯丝形状:双环/螺旋/笼状),泛泛比会误判SAME** ③配上用干净图(clean_match,最高保真)，配不上清该SKU海报出白底(poster_clean,身份由标签背书)，无锚点=none交人工。实测G125TBOA→clean_match正确、DS120180→正确否决错误圆球图并poster_clean出正确椭圆灯。**待办**：全量前需给resolve_source加①OCR按文件夹缓存②找到锚点早停(否则52个跑数小时)，再替换pipeline里的`pick_best_clean_shot`重跑。变体差异只在灯丝形状(TBOA双环/MOA螺旋/HBOA笼状,同G125球同尺寸)。output/products/里52个SKU图是未核对草稿。
