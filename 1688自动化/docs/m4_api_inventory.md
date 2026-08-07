# 1688 新版商品管理方案 · API 清单（自动抓取）

> 来源：[https://open.1688.com/solution/solutionDetail.htm?solutionKey=1671675923686](https://open.1688.com/solution/solutionDetail.htm?solutionKey=1671675923686)
> 抓取时间：本机运行 `test_m4_scrape_apis.py`
> 方案：新版商品管理解决方案（商家自用版）solutionKey=1671675923686

## 发布链路关键 API（优先实现）

| 用途 | APIName | 文档 |
|---|---|---|
| 类目搜索 | `alibaba.category.searchByKeyword` | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.category.searchByKeyword-1) |
| 类目详情 | `alibaba.category.get` | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.category.get-1) |
| 发布 Schema | `alibaba.new.product.getSchema` | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.new.product.getSchema-1) |
| 级联子 Schema | `alibaba.new.product.getSubSchema` | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.new.product.getSubSchema-1) |
| 新版发布 | `alibaba.new.product.add` | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.new.product.add-1) |
| 新版编辑 | `alibaba.new.product.edit` | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.new.product.edit-1) |
| 图片银行上传 | `alibaba.photobank.photo.add` | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.photobank.photo.add-1) |
| 相册列表 | `alibaba.photobank.album.getList` | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.photobank.album.getList-1) |
| 视频上传 | `alibaba.video.videocenter.upload` | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.multimedia:alibaba.video.videocenter.upload-1) |
| 视频查询 | `alibaba.video.videocenter.get` | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.multimedia:alibaba.video.videocenter.get-1) |
| 视频绑定 | `alibaba.video.videocenter.attach` | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.multimedia:alibaba.video.videocenter.attach-1) |
| 运费模板 | `alibaba.logistics.myFreightTemplate.list.get` | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.logistics:alibaba.logistics.myFreightTemplate.list.get-1) |
| 发货地址 | `alibaba.logistics.mySendGoodsAddress.list.get` | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.logistics:alibaba.logistics.mySendGoodsAddress.list.get-1) |

## 全量 API（方案页）

| APIName | 中文名 | 文档 |
|---|---|---|
| `albaba.video.videocenter.list` | 获取用户视频中心的视频列表 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.multimedia:albaba.video.videocenter.list-1) |
| `alibaba.category.get` | 根据类目Id查询类目 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.category.get-1) |
| `alibaba.category.searchByKeyword` | 商品发布 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.category.searchByKeyword-1) |
| `alibaba.logistics.freightTemplate.getList` | 物流相关 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.logistics:alibaba.logistics.freightTemplate.getList-1) |
| `alibaba.logistics.freightTemplate.operate.check` | 商品物流模板更换操作检测 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.logistics:alibaba.logistics.freightTemplate.operate.check-1) |
| `alibaba.logistics.myFreightTemplate.list.get` | 获取物流模板详情 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.logistics:alibaba.logistics.myFreightTemplate.list.get-1) |
| `alibaba.logistics.mySendGoodsAddress.list.get` | 我的发货地址列表 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.logistics:alibaba.logistics.mySendGoodsAddress.list.get-1) |
| `alibaba.member.brand.query` | 其他服务 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.member:alibaba.member.brand.query-1) |
| `alibaba.new.product.add` | 新版商品发布 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.new.product.add-1) |
| `alibaba.new.product.edit` | 新版商品编辑 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.new.product.edit-1) |
| `alibaba.new.product.getSchema` | 获取商品发布规则和详情 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.new.product.getSchema-1) |
| `alibaba.new.product.getSubSchema` | 获取商品发布级联子组件规则 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.new.product.getSubSchema-1) |
| `alibaba.photobank.album.add` | 创建相册 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.photobank.album.add-1) |
| `alibaba.photobank.album.delete` | 删除相册 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.photobank.album.delete-1) |
| `alibaba.photobank.album.getList` | 获取相册列表 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.photobank.album.getList-1) |
| `alibaba.photobank.album.getProfile` | 图片相册 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.photobank.album.getProfile-1) |
| `alibaba.photobank.album.modify` | 修改相册 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.photobank.album.modify-1) |
| `alibaba.photobank.photo.add` | 上传图片 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.photobank.photo.add-1) |
| `alibaba.photobank.photo.delete` | 删除图片 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.photobank.photo.delete-1) |
| `alibaba.photobank.photo.deleteBatch` | 批量删除图片 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.photobank.photo.deleteBatch-1) |
| `alibaba.photobank.photo.getList` | 获取图片列表 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.photobank.photo.getList-1) |
| `alibaba.photobank.photo.modify` | 修改图片信息 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.photobank.photo.modify-1) |
| `alibaba.processingCategory.get` | 根据类目Id查询加工定制类目 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.processingCategory.get-1) |
| `alibaba.product.delete` | 删除商品 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.delete-1) |
| `alibaba.product.expire` | 商品转为过期 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.expire-1) |
| `alibaba.product.get` | 获取商品 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.get-1) |
| `alibaba.product.getByIdList` | 根据商品ID列表获取商品(卖家) | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.getByIdList-1) |
| `alibaba.product.isModifiable` | 产品是否可以修改 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.isModifiable-1) |
| `alibaba.product.list.get` | 商品管理 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.list.get-1) |
| `alibaba.product.modifyQuickBackStock` | 修改商品快返库存 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.modifyQuickBackStock-1) |
| `alibaba.product.modifyStock` | 修改产品库存 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.modifyStock-1) |
| `alibaba.product.price.update` | 单独修改商品价格 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.price.update-1) |
| `alibaba.product.ptsTag.query` | 买家保障 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.ptsTag.query-1) |
| `alibaba.product.ptsTag.update` | 买家保障服务写入 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.ptsTag.update-1) |
| `alibaba.product.recommend.deleteProductGroup` | 删除一个推荐分组 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.recommend.deleteProductGroup-1) |
| `alibaba.product.recommend.editProductGroup` | 修改商家热推分组信息 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.recommend.editProductGroup-1) |
| `alibaba.product.recommend.queryList` | 组合推荐 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.recommend.queryList-1) |
| `alibaba.product.recommend.queryProductListByGroupId` | 根据groupId获取商品列表 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.recommend.queryProductListByGroupId-1) |
| `alibaba.product.recommend.saveProductGroup` | 保存用户推荐商品组合 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.recommend.saveProductGroup-1) |
| `alibaba.product.republish` | 未上架商品重新上架 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.product.republish-1) |
| `alibaba.productLines.get` | 获取用户产品线信息 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.productLines.get-1) |
| `alibaba.userCategory.list.get` | 获取授权用户的商品自定义分类列表 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.userCategory.list.get-1) |
| `alibaba.userDefine.category.add` | 自定义类目 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:alibaba.userDefine.category.add-1) |
| `alibaba.video.videocenter.attach` | 1688商品关联视频中心视频 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.multimedia:alibaba.video.videocenter.attach-1) |
| `alibaba.video.videocenter.delete` | 删除视频中心视频 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.multimedia:alibaba.video.videocenter.delete-1) |
| `alibaba.video.videocenter.detach` | 解绑视频和商品的关联关系 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.multimedia:alibaba.video.videocenter.detach-1) |
| `alibaba.video.videocenter.get` | 视频管理 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.multimedia:alibaba.video.videocenter.get-1) |
| `alibaba.video.videocenter.modify` | 修改视频中心视频 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.multimedia:alibaba.video.videocenter.modify-1) |
| `alibaba.video.videocenter.upload` | 上传视频至视频中心 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.multimedia:alibaba.video.videocenter.upload-1) |
| `alibaba.video.videocenter.videoCheck` | 视频中心存储空间检测 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.multimedia:alibaba.video.videocenter.videoCheck-1) |
| `bussiness.category.get` | 查询卖家所属经营大类 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:bussiness.category.get-1) |
| `bussiness.category.list` | 查询经营大类列表 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:bussiness.category.list-1) |
| `bussiness.category.update` | 更新卖家店铺经营大类 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:bussiness.category.update-1) |
| `com.alibaba.cbu.offer.quality.advice.query` | 商品质量 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:com.alibaba.cbu.offer.quality.advice.query-1) |
| `com.alibaba.cbu.offer.quality.advice.queryList` | 根据商品id列表获取质量星级优化建议 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:com.alibaba.cbu.offer.quality.advice.queryList-1) |
| `main.category.get` | 查询商家主营类目 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:main.category.get-1) |
| `main.content.publish` |  | — |
| `main.topic.query` |  | — |
| `offerGroup.hasOpened` | 获取用户是否开启自定义分类 | [文档](https://open.1688.com/api/apidocdetail.htm?id=cn.alibaba.open:offerGroup.hasOpened-1) |
| `offerGroup.set` | 开启或关闭自定义分类 | [文档](https://open.1688.com/api/apidocdetail.htm?id=cn.alibaba.open:offerGroup.set-1) |
| `privatedomain.content.publish` | 会员号内容 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.multimedia:privatedomain.content.publish-1) |
| `privatedomain.topic.query` | 话题查询 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.multimedia:privatedomain.topic.query-1) |
| `product.asyncQueryInfo.getInfo` | 商品发布异步信息查询 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:product.asyncQueryInfo.getInfo-1) |
| `product.increment.editInfo` | 新版商品增量编辑 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:product.increment.editInfo-1) |
| `product.quality.getInfo` | 获取商品质量星级相关信息 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:product.quality.getInfo-1) |
| `relative.category.list` | 获取关联经营类目列表 | [文档](https://open.1688.com/api/apidocdetail.htm?id=com.alibaba.product:relative.category.list-1) |
| `trade.order.batch.rate` | 批量提交订单评价 | [文档](https://open.1688.com/api/apidocdetail.htm?id=cn.alibaba.open:trade.order.batch.rate-1) |
| `userCategory.get.offerIds` | 获取商品自定义分类ID | [文档](https://open.1688.com/api/apidocdetail.htm?id=cn.alibaba.open:userCategory.get.offerIds-1) |
| `userCategory.offers.add` | 添加商品的自定义分类 | [文档](https://open.1688.com/api/apidocdetail.htm?id=cn.alibaba.open:userCategory.offers.add-1) |
| `userCategory.offers.remove` | 移除商品的自定义分类 | [文档](https://open.1688.com/api/apidocdetail.htm?id=cn.alibaba.open:userCategory.offers.remove-1) |

## 前端 JS SDK（方案页「开发人员参考」摘录）

```
(未抓到，见 open 方案页#developmentReference)
```

## 备注

- 发布强制配合前端 JS SDK（`pcAlgorithmSdk`），见 `docs/m4_findings.md`。
- 确切参数以各 API 文档页为准；本清单只作索引。
- 原始 JSON：`output/_m4/api_inventory.json`
