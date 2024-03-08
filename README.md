
<div align="center">

# OpenBMCLAPI for Python

![GitHub Issues or Pull Requests](https://img.shields.io/github/issues-pr/tianxiu2b2t/python-openbmclapi)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/tianxiu2b2t/python-openbmclapi)
![GitHub License](https://img.shields.io/github/license/tianxiu2b2t/python-openbmclapi)
![GitHub Release](https://img.shields.io/github/v/release/tianxiu2b2t/python-openbmclapi)
![GitHub Tag](https://img.shields.io/github/v/tag/tianxiu2b2t/python-openbmclapi)
![GitHub Downloads (all assets, latest release)](https://img.shields.io/github/downloads/tianxiu2b2t/python-openbmclapi/latest/total)
![GitHub Repo stars](https://img.shields.io/github/stars/tianxiu2b2t/python-openbmclapi)


✨ 基于 [OpenBMCLAPI](https://github.com/bangbang93/openbmclapi) 的 Python 实现。

🎨 **跨系统**、**跨架构**和 **Docker** 支持。

</div>

# 项目说明

本项目是 [OpenBMCLAPI](https://github.com/bangbang93/openbmclapi) 的 Python 版本，OpenBMCLAPI 是通过分布式集群帮助 [BMCLAPI](https://bmclapidoc.bangbang93.com/) 进行文件分发、加速中国大陆 Minecraft 下载的公益项目。

如果你想加入 OpenBMCLAPI，可以寻找 [bangbang93](https://github.com/bangbang93) 获取 `CLUSTER_ID` 和 `CLUSTER_SECRET`。

# 部署

## 从源码运行

1. 克隆仓库：

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

4. 在 `config.properties` 中，填写你的 `cluster.id`（即 `CLUSTER_ID`）和 `cluster.secret`（即 `CLUSTER_SECRET`）。

5. 重新启动程序。

## 使用 Docker 部署

1. 拉取镜像：

```sh
docker pull silianz/python-openbmclapi:latest
```

2. 创建容器：

```sh
docker run -d \
-v /data/python-openbmclapi:/python-openbmclapi/cache \
-v /path/to/your/config:/python-openbmclapi/config/config.properties \
-p ${web.port}:${web.port} \
--restart always \
--name python-openbmclapi \
silianz/python-openbmclapi 
```

> ![WARNING]
> Docker 容器仍在实验中，还未发布。

# 鸣谢

[LiterMC/go-openbmclapi](https://github.com/LiterMC/go-openbmclapi/)

[bangbang93/openbmclapi](https://github.com/bangbang93/openbmclapi/)
