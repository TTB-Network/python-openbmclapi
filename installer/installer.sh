#!/bin/bash


if [ "$(id -u)" -ne 0 ]; then
	echo -e "\e[31mERROR: Not root user\e[0m"
	exit 1
fi
MIRROR_PREFIX="https://mirror.ghproxy.com/"
echo "MIRROR_PREFIX=${MIRROR_PREFIX}"

REPO='TTB-Network/python-openbmclapi'
RAW_PREFIX="${MIRROR_PREFIX}https://raw.githubusercontent.com"
RAW_REPO="$RAW_PREFIX/$REPO"
BASE_PATH=/opt/py-openbmclapi
USERNAME=openbmclapi
PY_MIRCO=3.10
if ! PY_VERSION=$(python -V 2>&1|awk '{print $2}') && $(python -V 2>&1|awk '{print $2}'|awk -F '.' '{print $1}') -lt 3 ; then
    echo -e "\e[31mERROR: Failed to detect python version\e[0m"
    exit 1
fi
PY_VERSION=$(python -V 2>&1|awk '{print $2}'|awk -F '.' '{print $1}').$(python -V 2>&1|awk '{print $2}'|awk -F '.' '{print $2}')
different=$(echo 2>&1 | awk "{print $PY_VERSION - $PY_MIRCO}")
compare=$(expr "$different" \> 0)
#printf $compare
if  [[ $compare -eq 0 ]] ; then
    echo -e "\e[31mERROR: Python version not supported;need >=3.10\e[0m"
    exit 1
fi

if ! systemctl --version >/dev/null 2>&1 ; then
	echo -e "\e[31mERROR: Failed to test systemd\e[0m"
	exit 1
fi

if [ ! -d /usr/lib/systemd/system/ ]; then
	echo -e "\e[31mERROR: /usr/lib/systemd/system/ is not exist\e[0m"
	exit 1
fi

if ! id $USERNAME >/dev/null 2>&1; then
	echo -e "\e[34m==> Creating user $USERNAME\e[0m"
	useradd $USERNAME || {
		echo -e "\e[31mERROR: Could not create user $USERNAME\e[0m"
		exit 1
  	}
fi


function fetchGithubLatestTag(){
	prefix="location: https://github.com/$REPO/releases/tag/"
	location=$(curl -fsSI "https://github.com/$REPO/releases/latest" | grep "$prefix" | tr -d "\r")
	[ $? = 0 ] || return 1
	export LATEST_TAG="${location#${prefix}}"
}

function fetchBlob(){
	file=$1
	target=$2
	filemod=$3

	source="$RAW_REPO/master/$file"
	echo -e "\e[34m==> Downloading $source\e[0m"
	tmpf=$(mktemp -t py-openbmclapi.XXXXXXXXXXXX.downloading)
	curl -fsSL -o "$tmpf" "$source" || { rm "$tmpf"; return 1; }
	echo -e "\e[34m==> Downloaded $source\e[0m"
	mv "$tmpf" "$target" || return $?
	echo -e "\e[34m==> Installed to $target\e[0m"
	chown $USERNAME "$target"
	if [ -n "$filemod" ]; then
		chmod "$filemod" "$target" || return $?
	fi
}

echo

if [ -f /usr/lib/systemd/system/py-openbmclapi.service ]; then
	echo -e "\e[33m==> WARN: py-openbmclapi.service is already installed, stopping\e[0m"
	systemctl disable --now py-openbmclapi.service
fi

if [ -z "$TARGET_TAG" ]; then
	echo -e "\e[34m==> Fetching latest tag for https://github.com/$REPO\e[0m"
	fetchGithubLatestTag
	TARGET_TAG=$LATEST_TAG
	echo
	echo -e "\e[32m*** py-openbmclapi LATEST TAG: $TARGET_TAG ***\e[0m"
	echo
fi

fetchBlob installer/py-openbmclapi.service /usr/lib/systemd/system/py-openbmclapi.service 0644 || exit $?

[ -d "$BASE_PATH" ] || { mkdir -p "$BASE_PATH" && chmod 0755 "$BASE_PATH" && chown $USERNAME "$BASE_PATH"; } || exit $?

fetchBlob installer/start.sh "$BASE_PATH/start.sh" 0755 || exit $?
# fetchBlob service/stop-server.sh "$BASE_PATH/stop-server.sh" 0755 || exit $?
# fetchBlob service/reload-server.sh "$BASE_PATH/reload-server.sh" 0755 || exit $?
#https://github.com/TTB-Network/python-openbmclapi/archive/refs/tags/v1.10.4-907d74f.tar.gz
source="${MIRROR_PREFIX}https://github.com/$REPO/archive/refs/tags/$TARGET_TAG.tar.gz"
echo -e "\e[34m==> Downloading $source\e[0m"

curl -fsSL -o "/tmp/py-obai-latest.tar.gz" "$source"
#curl "$source" /tmp/py-obai-latest.tar.gz 0755 || exit $?
tar -zxvf /tmp/py-obai-latest.tar.gz --strip-components 1 -C $BASE_PATH
chown -R openbmclapi "$BASE_PATH"
chmod -R 766 "$BASE_PATH"
echo -e "\e[34m==> Installing Python modules\e[0m"
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r /opt/py-openbmclapi/requirements.txt --break-system-packages
echo -e "\e[34m==> Enabling py-openbmclapi.service\e[0m"
systemctl enable py-openbmclapi.service || exit $?

echo -e "
================================ Install successed ================================
	\e[37;41m Please check config in /opt/py-openbmclapi/config/config.yml \033[0m
  Use 'systemctl start py-openbmclapi.service' to start openbmclapi server
  Use 'systemctl stop py-openbmclapi.service' to stop openbmclapi server
  Use 'systemctl reload py-openbmclapi.service' to reload openbmclapi server configs
  Use 'journalctl -f --output cat -u py-openbmclapi.service' to watch the openbmclapi logs
"
