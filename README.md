<div align="center">

# OpenBMCLAPI for Python v4

Python-OpenBMCLAPI v4 的发布！

简体中文 | [English](/i18n/README_en.md)

![GitHub Issues or Pull Requests](https://img.shields.io/github/issues-pr/TTB-Network/python-openbmclapi)
![GitHub Issues or Pull Requests](https://img.shields.io/github/issues/TTB-Network/python-openbmclapi)
![GitHub License](https://img.shields.io/github/license/TTB-Network/python-openbmclapi)
![GitHub Release](https://img.shields.io/github/v/release/TTB-Network/python-openbmclapi)
![GitHub Tag](https://img.shields.io/github/v/tag/TTB-Network/python-openbmclapi)
![Docker Pulls](https://img.shields.io/docker/pulls/silianz/python-openbmclapi)
[![Crowdin](https://badges.crowdin.net/python-openbmclapi-site/localized.svg)](https://crowdin.com/project/python-openbmclapi-site)
![GitHub Repo stars](https://img.shields.io/github/stars/TTB-Network/python-openbmclapi)
[![CodeQL](https://github.com/TTB-Network/python-openbmclapi/actions/workflows/github-code-scanning/codeql/badge.svg)](https://github.com/TTB-Network/python-openbmclapi/actions/workflows/github-code-scanning/codeql)
[![Create tagged release](https://github.com/TTB-Network/python-openbmclapi/actions/workflows/build_and_publish.yml/badge.svg)](https://github.com/TTB-Network/python-openbmclapi/actions/workflows/build_and_publish.yml)

[赞助](https://afdian.net/a/atianxiua)

✨ 基于 [OpenBMCLAPI](https://github.com/bangbang93/openbmclapi) 的 Python 实现。

🎨 **跨系统**、**跨架构**。这得益于 Python 强大的语言功能。

✨ **Docker** 支持。通过 Docker 更加**快捷地**部署 python-openbmclapi ~~（更支持一键跑路）~~。

</div>

# 简介

本项目是 [OpenBMCLAPI](https://github.com/bangbang93/openbmclapi) 的 Python 版本，OpenBMCLAPI 是通过分布式集群帮助 [BMCLAPI](https://bmclapidoc.bangbang93.com/) 进行文件分发、加速中国大陆 Minecraft 下载的公益项目。

如果你想加入 OpenBMCLAPI，可以寻找 [bangbang93](https://github.com/bangbang93) 获取 `CLUSTER_ID` 和 `CLUSTER_SECRET`。

# 贡献

如果你有能力，你可以向我们的仓库提交 Pull Request 或 Issue。

如果你想帮助我们进行多语言翻译，请前往 [Crowdin](https://translate.bugungu.top)。

在贡献之前，请先阅读我们的[贡献准则](./CONTRIBUTING.md)。

# 鸣谢

[LiterMC/go-openbmclapi](https://github.com/LiterMC/go-openbmclapi)

[bangbang93/openbmclapi](https://github.com/bangbang93/openbmclapi)

[SALTWOOD/CSharp-OpenBMCLAPI](https://github.com/SALTWOOD/CSharp-OpenBMCLAPI)

# 快速开始

1. 安装依赖

```bash
pip install -r requirements.txt
```

2. 首次运行脚本生成配置文件 
```yaml
advanced:
  access_log: false
  debug: false
  host: ''
  locale: zh_cn
cert:
  cert: null
  dir: .ssl
  key: null
web:
  port: 6543
  proxy: false
  public_port: 6543
```

3. 修改配置文件（例子）
```yaml
advanced:
  access_log: false
  debug: false
  host: ''
  locale: zh_cn
cert:
  cert: null
  dir: .ssl
  key: null
web:
  port: 6543
  proxy: false
  public_port: 6543
clusters:
  - id: # 670... 
    secret: # <你的节点密钥>
  # 需要增加多个节点如下
  # - id: # 670...
  #   secret: # <你的节点密钥>
storages:
  # local
  - name: bmclapi # 存储名字
    type: local 
    path: /bmclapi
    weight: 1
  # alist
  - name: alist
    type: alist
    path: /path/to/your/alist
    endpoint: http://127.0.0.1:5244
    username: admin
    password: password
    weight: 1
  # alist 下的 WebDav
  - name: alist-webdav
    type: webdav
    path: /path/to/your/alist
    endpoint: http://127.0.0.1:5244/dav
    username: admin
    password: password
    weight: 1
  # s3
  - name: s3
    type: s3
    path: /path/to/your/s3
    endpoint: https://s3.amazonaws.com
    access_key: <你的access_key>
    secret_key: <你的secret_key>
    bucket: <你的bucket>
    weight: 1
    # 可选
    # 例子 
    # custom_s3_host: bmclapi-files.ttb-network.top
    # public_endpoint: https://s3.ttb-network.top
```

4. 开始 for Windows
```bash
python main.py
```

4. 开始 for Docker
```bash
docker run -d --restart=always -p 6543:6543 -v /path/to/your/config.yaml:/app/config.yaml -v /path/to/your/bmclapi:/app/bmclapi --name python-openbmclapi atianxiua/python-openbmclapi:latest
```

# TODO
- [ ] 文档
- [ ] 面板