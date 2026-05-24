# 排障

## 服务启动但没有消息

- 检查企业微信回调地址是否正确。
- 检查 `WECOM_TOKEN`、`WECOM_ENCODING_AES_KEY`、`WECOM_CORP_ID`。
- 检查 `WECOM_APP_SECRET` 是否为会话内容存档 Secret。
- 检查 `source_cursors` 和 `/app/data/.wecom_seq` 是否停在旧游标。

## SDK 初始化失败

- 检查容器架构和 `lib/` 下 SDK 是否匹配。
- 检查 `private_key.pem` 是否挂载到容器内。
- Mac 本地可设置 `WECOM_DISABLE_SDK=true` 先跑 API 层。

## Obsidian 没有写入

- 检查 `/notes` volume 是否挂载到正确 vault。
- 检查 `/admin/destinations` 和 `/admin/routes` 是否存在匹配配置。
- 检查 `/admin/deliveries?status=failed` 的错误信息。

## Craft 投递失败

- 检查 `link_id`、`document_id`、`token`。
- 使用 `POST /bindings/verify` 或 target `verify()` 验证目标。
- 检查 Craft API 是否返回 404、429 或 deprecated 提示。
