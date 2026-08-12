# P0.7 渠道 GMV 拆解 POC 结论文档模板
# 文件路径：docs/TK-P0.7-渠道GMV拆解-POC结论.md

# TK · P0.7 渠道 GMV 拆解 POC 结论
> 日期：2026-08-10  
> 对应计划：[TK-整体开发计划](./TK-整体开发计划.md) · P0.7

## 1. 目标
验证**店铺数据分析页「GMV 拆解」**能否稳定抓取直播 / 视频 / 商品卡占比。

## 2. 所需文件
- `collectors/tiktok-ads/scripts/scrape-gmv-split-page.js`
- `collectors/tiktok-ads/scripts/run-gmv-split-poc.ps1`
- `docs/TK-P0.7-渠道GMV拆解-POC结论.md`

## 3. 执行步骤
```powershell
cd collectors\tiktok-ads
.\scripts\run-gmv-split-poc.ps1 -StoreId=27501502216807
```

## 4. 验证项
- [ ] 能打开店铺数据分析页
- [ ] 能抓取「GMV 拆解」区域
- [ ] 字段稳定（直播占比、视频占比、商品卡占比、总 GMV）
- [ ] 样例 JSON 入 logs/gmvsplit-*.json

## 5. 验收结论
- **通过** → 补列到 `fact_tiktok_shop_daily` 或旁路日表
- **部分通过** → 直播/视频可采，商品卡不可采
- **不通过** → 冻结，① 渠道结构异动异常不开

## 6. 门禁 Verdict
**Verdict：🟢 采集通过（2026-08-10）**  
下一刀：P0.7 正式开发（schema + ingest + 规则）