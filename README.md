<div align="center">

![](https://github.com/TTB-Network/python-openbmclapi/assets/113701655/5b554658-b057-4111-85c3-9d1eb5b32975)

# OpenBMCLAPI for Python

![GitHub Issues or Pull Requests](https://img.shields.io/github/issues-pr/TTB-Network/python-openbmclapi)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/TTB-Network/python-openbmclapi)
![GitHub License](https://img.shields.io/github/license/TTB-Network/python-openbmclapi)
![GitHub Release](https://img.shields.io/github/v/release/TTB-Network/python-openbmclapi)
![GitHub Tag](https://img.shields.io/github/v/tag/TTB-Network/python-openbmclapi)
![GitHub Repo stars](https://img.shields.io/github/stars/TTB-Network/python-openbmclapi)
[![CodeQL](https://github.com/TTB-Network/python-openbmclapi/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/TTB-Network/python-openbmclapi/actions/workflows/github-code-scanning/codeql)
[![Create tagged release](https://github.com/TTB-Network/python-openbmclapi/actions/workflows/build_and_publish.yml/badge.svg)](https://github.com/TTB-Network/python-openbmclapi/actions/workflows/build_and_publish.yml)

✨ 基于 [OpenBMCLAPI](https://github.com/bangbang93/openbmclapi) 的 Python 实现。

🎨 **跨系统**、**跨架构**。这得益于 Python 强大的语言功能。

✨ **Docker** 支持。通过 Docker 更加**快捷地**部署 python-openbmclapi ~~（更支持一键跑路）~~

🌈 __*新增功能！*__ **插件拓展**支持。你可以更方便地为 python-openbmclapi 编写自己的插件。

🎉 __*新增功能！*__ 基于 Echart 的 OpenBMCLAPI 仪表盘（Dashboard）。

🎉 __*新增功能！*__ 基于 loguru 的**日志器**。

</div>

# 简介

本项目是 [OpenBMCLAPI](https://github.com/bangbang93/openbmclapi) 的 Python 版本，OpenBMCLAPI 是通过分布式集群帮助 [BMCLAPI](https://bmclapidoc.bangbang93.com/) 进行文件分发、加速中国大陆 Minecraft 下载的公益项目。

如果你想加入 OpenBMCLAPI，可以寻找 [bangbang93](https://github.com/bangbang93) 获取 `CLUSTER_ID` 和 `CLUSTER_SECRET`。

# 部署

## 从源码运行

1. 克隆仓库或从 [Releases](https://github.com/TTB-Network/python-openbmclapi/releases) 中下载代码：

    ```sh
    git clone https://github.com/tianxiu2b2t/python-openbmclapi.git
    cd python-openbmclapi
    ```

2. 安装依赖：

    ```sh
    pip install -r --no-deps requirements.txt
    ```

    > 你可能需要先安装 [Microsoft C++ 生成工具](https://visualstudio.microsoft.com/visual-cpp-build-tools/)。

3. 运行一次主程序生成配置文件：

    ```sh
    python main.py
    ```

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
    -e web.public_port=${web.public_port} \
    -p ${web.public_port}:8080 \
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
  # 新连接读取数据头大小
  header_bytes: 4096
  # 数据传输缓存大小
  io_buffer: 16777216
  # 最小读取速率（Bytes）
  min_rate: 500
  # 最小读取速率时间
  min_rate_timestamp: 1000
  # 请求缓存大小
  request_buffer: 8192
  # 超时时间
  timeout: 30
cluster:
  # 是否不使用 BMCLAPI 分发的证书, 同 CLUSTER_BYOC
  byoc: false
  # OpenBMCLAPI 的 CLUSTER_ID
  id: ''
  # 实际开放的公网主机名, 同 CLUSTER_IP
  public_host: ''
  # 实际开放的公网端口, 同 CLUSTER_PUBLIC_PORT
  public_port: 8800
  # OpenBMCLAPI 的 CLUSTER_SECRET
  secret: ''
download:
  # 最高下载线程
  threads: 64
web:
  # 要监听的本地端口, 同 CLUSTER_PORT
  port: 80
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
