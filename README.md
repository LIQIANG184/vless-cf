# EDtunnel
Use Cloudflare pages and worker serverless to implement VLESS protocol.

<br>

## Deploy in pages.dev
1. See YouTube Video: [https://www.youtube.com/watch?v=8I-yTNHB0aw](https://www.youtube.com/watch?v=8I-yTNHB0aw)
2. Clone this repository deploy in cloudflare pages.

## Deploy in worker.dev
1. Copy `_worker.js` code from [here](https://github.com/Vauth/vless-cf/blob/main/_worker.js).
2. Alternatively, you can click the button below to deploy directly.

[![Deploy to Cloudflare Workers](https://deploy.workers.cloudflare.com/button)](https://deploy.workers.cloudflare.com/?url=https://github.com/Vauth/vless-cf)


## DoH with Cloudflare
1. Follow the https://github.com/serverless-dns/serverless-dns .
2. Replace the dns url with `dohURL` value in `_worker.js` .

## UUID Setting (Optional)

1. When deploy in cloudflare pages, you can set uuid in `wrangler.toml` file. variable name is `UUID`. `wrangler.toml` file is also supported. (recommended) in case deploy in webpages, you can not set uuid in `wrangler.toml` file.

2. When deploy in worker.dev, you can set uuid in `_worker.js` file. variable name is `userID`. `wrangler.toml` file is also supported. (recommended) in case deploy in webpages, you can not set uuid in `wrangler.toml` file. in this case, you can also set uuid in `UUID` enviroment variable.

Note: `UUID` is the uuid you want to set. pages.dev and worker.dev all of them method supported, but depend on your deploy method.

### UUID Setting Example

1. single uuid environment variable

   ```.environment
   UUID = "uuid here your want to set"
   ```

2. multiple uuid environment variable

   ```.environment
   UUID = "uuid1,uuid2,uuid3"
   ```

   note: uuid1, uuid2, uuid3 are separated by commas`,`.
   when you set multiple uuid, you can use `https://edtunnel.pages.dev/uuid1` to get the clash config and vless:// link.

## subscribe vless:// link (Optional)

1. visit `https://edtunnel.pages.dev/uuid your set` to get the subscribe link.

2. visit `https://edtunnel.pages.dev/sub/uuid your set` to get the subscribe content with `uuid your set` path.

   note: `uuid your set` is the uuid you set in UUID enviroment or `wrangler.toml`, `_worker.js` file.
   when you set multiple uuid, you can use `https://edtunnel.pages.dev/sub/uuid1` to get the subscribe content with `uuid1` path.(only support first uuid in multiple uuid set)

3. visit `https://edtunnel.pages.dev/sub/uuid your set/?format=clash` to get the subscribe content with `uuid your set` path and `clash` format. content will return with base64 encode.

   note: `uuid your set` is the uuid you set in UUID enviroment or `wrangler.toml`, `_worker.js` file.
   when you set multiple uuid, you can will use `https://edtunnel.pages.dev/sub/uuid1/?format=clash` to get the subscribe content with `uuid1` path and `clash` format.(only support first uuid in multiple uuid set)

## subscribe Cloudflare bestip(pure ip) link

1. visit `https://edtunnel.pages.dev/bestip/uuid your set` to get subscribe info.

2. cpoy subscribe url link `https://edtunnel.pages.dev/bestip/uuid your set` to any clients(clash/v2rayN/v2rayNG) you want to use.

3. done. if have any questions please join [@edtunnel](https://t.me/edtunnel)

## multiple port support (Optional)

   <!-- let portArray_http = [80, 8080, 8880, 2052, 2086, 2095];
	let portArray_https = [443, 8443, 2053, 2096, 2087, 2083]; -->

For a list of Cloudflare supported ports, please refer to the [official documentation](https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/ports).

By default, the port is 80 and 443. If you want to add more ports, you can use the following ports:

```text
80, 8080, 8880, 2052, 2086, 2095, 443, 8443, 2053, 2096, 2087, 2083
http port: 80, 8080, 8880, 2052, 2086, 2095
https port: 443, 8443, 2053, 2096, 2087, 2083
```

if you deploy in cloudflare pages, https port is not supported. Simply add multiple ports node drictly use subscribe link, subscribe content will return all Cloudflare supported ports.

## proxyIP (Optional)

1. When deploy in cloudflare pages, you can set proxyIP in `wrangler.toml` file. variable name is `PROXYIP`.

2. When deploy in worker.dev, you can set proxyIP in `_worker.js` file. variable name is `proxyIP`.

note: `proxyIP` is the ip or domain you want to set. this means that the proxyIP is used to route traffic through a proxy rather than directly to a website that is using Cloudflare's (CDN). if you don't set this variable, connection to the Cloudflare IP will be cancelled (or blocked)...

resons: Outbound TCP sockets to Cloudflare IP ranges are temporarily blocked, please refer to the [tcp-sockets documentation](https://developers.cloudflare.com/workers/runtime-apis/tcp-sockets/#considerations)

## 候选 IP 获取与测速

### 获取候选 IPv4

从 `cf.vvhan.com` 获取候选 IP，并保存到 `cf-ips.txt`：

```bash
python3 scripts/fetch_cf_ips.py
```

也可以指定输出文件：

```bash
python3 scripts/fetch_cf_ips.py --output my-cf-ips.txt
```

### 测试候选 IP

HTTP/HTTPS 测试：

```bash
python3 scripts/cf_ip_benchmark.py \\
  --host your-worker.workers.dev \\
  --input cf-ips.txt \\
  --port 443 \\
  --http
```

WebSocket 测试：

```bash
python3 scripts/cf_ip_benchmark.py \\
  --host your-worker.workers.dev \\
  --input cf-ips.txt \\
  --port 80 \\
  --timeout 5
```

常用端口如下：

```text
HTTP：80、8080、8880、2052、2086、2095
HTTPS：443、8443、2053、2096、2087、2083
```

### 生成 Clash 配置

HTTP WebSocket：

```bash
python3 scripts/cf_ip_benchmark.py \\
  --host your-worker.workers.dev \\
  --input cf-ips.txt \\
  --port 80 \\
  --timeout 5 \\
  --uuid your-uuid \\
  --clash-output cf-best.yaml
```

HTTPS WebSocket：

```bash
python3 scripts/cf_ip_benchmark.py \\
  --host your-worker.workers.dev \\
  --input cf-ips.txt \\
  --port 443 \\
  --timeout 5 \\
  --uuid your-uuid \\
  --clash-output cf-best.yaml
```

参数说明：

- `--host`：Worker 域名。
- `--input`：候选 IP 文件。
- `--port`：测试端口，可重复指定。
- `--timeout`：单个 IP 的超时时间，单位为秒。
- `--uuid`：VLESS UUID。
- `--clash-output`：Clash 配置输出文件。
- `--http`：使用 HTTP 状态码测试，不加此参数时测试 WebSocket。

### 配置 Worker

在 `wrangler.toml` 中设置 UUID：

```toml
[vars]
UUID = "your-uuid"
PROXYIP = "your-proxy-ip-or-domain"
```

部署 Worker：

```bash
npm install
npm run deploy
```

### 获取订阅配置

将下面的域名和 UUID 替换为实际值：

```text
https://your-domain.example/your-uuid
https://your-domain.example/sub/your-uuid?format=clash
https://your-domain.example/bestip/your-uuid
```

### 完整操作流程

```bash
python3 scripts/fetch_cf_ips.py

python3 scripts/cf_ip_benchmark.py \\
  --host your-worker.workers.dev \\
  --input cf-ips.txt \\
  --port 80 \\
  --timeout 5 \\
  --uuid your-uuid \\
  --clash-output cf-best.yaml
```

将生成的 `cf-best.yaml` 导入 Clash 即可使用。配置默认包含以下规则：

- Hagezi 广告/跟踪域名：拒绝连接。
- `category-ads-all` 广告域名：拒绝连接。
- 中国大陆 IP：直连。
- 其他流量：使用 `CF-BEST` 代理组。

## Star History

[![GitHub stars](https://img.shields.io/github/stars/LIQIANG184/vless-cf?style=flat-square)](https://github.com/LIQIANG184/vless-cf/stargazers)

[在 Star History 查看仓库趋势](https://www.star-history.com/#LIQIANG184/vless-cf&Date)
