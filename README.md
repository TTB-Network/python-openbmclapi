<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="https://d.kstore.space/download/7507/logo_dark.svg">
  <source media="(prefers-color-scheme: light)" srcset="https://d.kstore.space/download/7507/logo_light.svg">
  <img alt="logo" src="https://d.kstore.space/download/7507/logo_light.svg" height=400>
</picture>

# OpenBMCLAPI for Python

![GitHub Issues or Pull Requests](https://img.shields.io/github/issues-pr/TTB-Network/python-openbmclapi)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/TTB-Network/python-openbmclapi)
![GitHub License](https://img.shields.io/github/license/TTB-Network/python-openbmclapi)
![GitHub Release](https://img.shields.io/github/v/release/TTB-Network/python-openbmclapi)
![GitHub Tag](https://img.shields.io/github/v/tag/TTB-Network/python-openbmclapi)
![GitHub Repo stars](https://img.shields.io/github/stars/TTB-Network/python-openbmclapi)
[![CodeQL](https://github.com/TTB-Network/python-openbmclapi/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/TTB-Network/python-openbmclapi/actions/workflows/github-code-scanning/codeql)
[![Create tagged release](https://github.com/TTB-Network/python-openbmclapi/actions/workflows/build_and_publish.yml/badge.svg)](https://github.com/TTB-Network/python-openbmclapi/actions/workflows/build_and_publish.yml)

[文档](https://python-openbmclapi.ttb-network.top/) | [API](https://python-openbmclapi.ttb-network.top/docs/api) | [赞助](https://afdian.net/a/atianxiua)

✨ 基于 [OpenBMCLAPI](https://github.com/bangbang93/openbmclapi) 的 Python 实现。

🎨 **跨系统**、**跨架构**。这得益于 Python 强大的语言功能。

✨ **Docker** 支持。通过 Docker 更加**快捷地**部署 python-openbmclapi ~~（更支持一键跑路）~~。

🎉 __*新增功能！*__ WebDAV 支持。通过基于 Web 的分布式编写和版本控制（英语：Web-based Distributed Authoring and Versioning，缩写：WebDAV），用户可以协同编辑和管理存储在万维网服务器文件。


</div>

# 简介

本项目是 [OpenBMCLAPI](https://github.com/bangbang93/openbmclapi) 的 Python 版本，OpenBMCLAPI 是通过分布式集群帮助 [BMCLAPI](https://bmclapidoc.bangbang93.com/) 进行文件分发、加速中国大陆 Minecraft 下载的公益项目。

如果你想加入 OpenBMCLAPI，可以寻找 [bangbang93](https://github.com/bangbang93) 获取 `CLUSTER_ID` 和 `CLUSTER_SECRET`。

# 部署

## 从源码运行

建议 Python 版本：3.10+。

1. 克隆仓库或从 [Releases](https://github.com/TTB-Network/python-openbmclapi/releases) 中下载代码：

    ```sh
    git clone https://github.com/tianxiu2b2t/python-openbmclapi.git
    cd python-openbmclapi
    ```

    仓库镜像地址：https://gitee.com/ttb-network/python-openbmclapi

2. 安装依赖：

    ```sh
    pip install --no-deps -r requirements.txt
    ```

    > 你可能需要先安装 [Microsoft C++ 生成工具](https://visualstudio.microsoft.com/visual-cpp-build-tools/)。

3. 运行一次主程序生成配置文件：

    ```sh
    python main.py
    ```

    如果你看到以下报错信息：`core.exceptions.ClusterIdNotSet`，那么你就可以进行下一步的配置。

4. 在 `config/config.yml` 中，填写你的 `id`（即 `CLUSTER_ID`）和 `secret`（即 `CLUSTER_SECRET`）。

5. 重新启动程序。

## 使用 Docker 部署

1. 拉取镜像：

    ```sh
    docker pull silianz/python-openbmclapi:latest
    ```

    你也可使用镜像源进行拉取：

    ```sh
    docker pull registry.cn-hangzhou.aliyuncs.com/silianz/python-openbmclapi:latest
    ```

2. 创建容器：

    ```sh
    docker run -d \
    -v ${/path/to/your/cache}:/opt/python-openbmclapi/bmclapi \
    -e cluster.id=${cluster.id} \
    -e cluster.secret=${cluster.secret} \
    -e cluster.public_port=${cluster.public_port} \
    -p ${cluster.public_port}:8080 \
    --restart always \
    --name python-openbmclapi \
    silianz/python-openbmclapi 
    ```

    **参数说明：**

    `web.public_port` - 对外开放的端口。

    `cluster.id` - 即 `CLUSTER_ID`。

    `cluster.secret` - 即 `CLUSTER_SECRET`。

    `/path/to/your/cache` - `bmclapi` 文件夹（即缓存 `cache` 文件夹）挂载的路径。

## 配置文件

```yml
advanced:
  # 是否启用调试模式
  debug: false
  # 新连接读取数据头大小
  header_bytes: 4096
  # 数据传输缓存大小
  io_buffer: 16777216
  # 语言
  language: zh_cn
  # 最小读取速率（Bytes）
  min_rate: 500
  # 最小读取速率时间
  min_rate_timestamp: 1000
  # 请求缓存大小
  request_buffer: 8192
  # 超时时间
  timeout: 30
  # 是否跳过签名检测
  skip_sign: false
file:
  # 文件检查模式，可选值为 exists（检查文件是否存在，不推荐）、
  # size（检查文件大小）和 hash（检查文件哈希值）
  check: size
cache:
  # 缓存大小（Bytes）
  buffer: 536870912
  # 检查过时文件时间，单位为秒
  check: 360
  # 文件存在时间，单位为秒
  time: 1800
cluster:
  # 是否不使用 BMCLAPI 分发的证书, 同 CLUSTER_BYOC
  byoc: false
  # OpenBMCLAPI 的 CLUSTER_ID
  id: ''
  # 实际开放的公网主机名, 同 CLUSTER_IP
  public_host: ''
  # 实际开放的公网端口, 同 CLUSTER_PUBLIC_PORT
  public_port: 8800
  # 重连
  reconnect:
    # 重试间隔
    delay: 5
    # 重试次数，-1 为无限次数
    retry: -1
  # OpenBMCLAPI 的 CLUSTER_SECRET
  secret: ''
  # 超时设置
  timeout:
    # 发送启用数据包超时时间
    enable: 120
dashboard:
  # 仪表盘密码
  password: '123456'
  # 仪表盘用户名
  username: admin
download:
  # 最高下载线程
  threads: 64
# 存储设置
storages:
  bmclapi: # 你的存储名字
    # 存储路径
    path: ./bmclapi 
    # 存储类型，可选值为 file（本地存储）和 webdav（WebDAV）
    type: file 
    # 选用存储下载权重，-1 为禁用，不选择，但会下载文件
    width: 0 
  bmclapi_webdav: 
    path: /bmclapidev
    type: webdav
    width: 2 
    # 你的 WebDAV 端点
    endpoint: http://localhost:5244/dav
    # WebDAV 用户名
    username: user
    # WebDAV 用户密码
    password: password
web:
  # 是否强制使用 SSL
  force_ssl: false
  # 要监听的本地端口, 同 CLUSTER_PORT
  port: 8080
  # 服务器名字
  server_name: TTB-Network
  # SSL 端口
  ssl_port: 8800
```

# 贡献

如果你有能力，你可以向我们的[团队](mailto://administrator@ttb-network.top)或[团队所有者](mailto://silian_zheng@outlook.com)发送邮件并申请加入开发者行列。

# 鸣谢

[LiterMC/go-openbmclapi](https://github.com/LiterMC/go-openbmclapi)

[bangbang93/openbmclapi](https://github.com/bangbang93/openbmclapi)

[SALTWOOD/CSharp-OpenBMCLAPI](https://github.com/SALTWOOD/CSharp-OpenBMCLAPI)
