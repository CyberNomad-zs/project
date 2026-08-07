# 获取公司的店铺ID列表

## 需要开通的权限点

公司的账号信息权限

## 接口地址

/app/store/listIdByCompany

## 请求方式

POST

## content-type

application/json

## 接口描述

获取公司的店铺ID列表（使用应用授权令牌）

## 请求参数

### Headers

| 参数名称 | 参数值 | 参数说明 | 是否必须 |
| :--- | :--- | :--- | :--- |
| Content-Type | application/json |  | true |
| Authorization | Bearer API Key | | true |

### Query

无

### Body

| 参数名称 | 参数说明 | 请求类型 | 是否必须 | 数据类型 |
| :--- | :--- | :--- | :--- | :--- |
| companyId | 公司id |  | true | string |

## 公共响应参数

| 参数名称 | 参数说明 | 类型 |
| :--- | :--- | :--- |
| request_id | 全局请求id，方便追踪定位 | string |
| code | 网关返回码，0表示成功 | string |
| msg | 网关返回码描述 | string |
| sub_code | 业务返回码，成功时不返回 | string |
| sub_msg | 业务返回码描述，成功时不返回 | string |
| data | 业务响应参数 | string |

## 响应参数

| 参数名称 | 参数说明 | 类型 |
| :--- | :--- | :--- |
| storeCount | 店铺数量 | integer |
| storeList | 店铺id列表 | array |
| &nbsp;&nbsp;└  |  | integer |

## 响应状态

| 状态码 | 说明 |
| :--- | :--- |
| 暂无数据 | |

## 请求示例

```bash
curl --location 'https://sbappstoreapi.ziniao.com/openapi-router/app/store/listIdByCompany' \
--header 'Authorization: Bearer API Key' \
--header 'Content-Type: application/json' \
--data-raw '{"companyId":""}'
```

## 响应示例

```json
{
	"storeCount":"",
	"storeList":[
		""
	]
}
```
