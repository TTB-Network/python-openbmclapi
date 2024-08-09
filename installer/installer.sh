#!/bin/bash
# A script to install python-openbmclapi (modified from go-openbmclapi)
# Copyright (C) 2024 The co-author of go-openbmclapi

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.


if [ "$(id -u)" -ne 0 ]; then
	echo -e "\e[31mERROR: Not root user\e[0m"
	exit 1
fi
MIRROR_PREFIX="https://ghproxy.bugungu.top/"
echo "MIRROR_PREFIX=${MIRROR_PREFIX}"

REPO='TTB-Network/python-openbmclapi'
RAW_PREFIX="${MIRROR_PREFIX}https://raw.githubusercontent.com"
RAW_REPO="$RAW_PREFIX/$REPO"
BASE_PATH=/opt/python-openbmclapi
USERNAME=openbmclapi
PY_MIRCO=3.10
if ! PY_VERSION=$(python -V 2>&1|awk '{print $2}') && $(python -V 2>&1|awk '{print $2}'|awk -F '.' '{print $1}') -lt 3 ; then
    echo -e "\e[31mERROR: Failed to detect Python version.\e[0m"
    exit 1
fi
PY_VERSION=$(python -V 2>&1|awk '{print $2}'|awk -F '.' '{print $1}').$(python -V 2>&1|awk '{print $2}'|awk -F '.' '{print $2}')

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
	tmpf=$(mktemp -t python-openbmclapi.XXXXXXXXXXXX.downloading)
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

if [ -f /usr/lib/systemd/system/python-openbmclapi.service ]; then
	echo -e "\e[33m==> WARN: python-openbmclapi.service is already installed, stopping\e[0m"
	systemctl disable --now python-openbmclapi.service
fi

if [ -z "$TARGET_TAG" ]; then
	echo -e "\e[34m==> Fetching latest tag for https://github.com/$REPO\e[0m"
	fetchGithubLatestTag
	TARGET_TAG=$LATEST_TAG
	echo
	echo -e "\e[32m*** python-openbmclapi LATEST TAG: $TARGET_TAG ***\e[0m"
	echo
fi

fetchBlob installer/python-openbmclapi.service /usr/lib/systemd/system/python-openbmclapi.service 0644 || exit $?

[ -d "$BASE_PATH" ] || { mkdir -p "$BASE_PATH" && chmod 0755 "$BASE_PATH" && chown $USERNAME "$BASE_PATH"; } || exit $?

fetchBlob installer/start.sh "$BASE_PATH/start.sh" 0755 || exit $?
source="${MIRROR_PREFIX}https://github.com/$REPO/archive/refs/tags/$TARGET_TAG.tar.gz"
echo -e "\e[34m==> Downloading $source\e[0m"

curl -fsSL -o "/tmp/python-openbmclapi-latest.tar.gz" "$source"
tar -zxvf /tmp/python-openbmclapi-latest.tar.gz --strip-components 1 -C $BASE_PATH
chown -R openbmclapi "$BASE_PATH"
chmod -R 766 "$BASE_PATH"
echo -e "\e[34m==> Installing Python modules\e[0m"
python3 -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r /opt/python-openbmclapi/requirements.txt
echo -e "\e[34m==> Enabling python-openbmclapi.service\e[0m"
systemctl enable python-openbmclapi.service || exit $?

echo -e "
=================================== Successfully installed ===================================
	\e[37;41m Please check config in /opt/python-openbmclapi/config/config.yml \033[0m
  Use 'systemctl start python-openbmclapi.service' to start python-openbmclapi service
  Use 'systemctl stop python-openbmclapi.service' to stop python-openbmclapi service
  Use 'systemctl reload python-openbmclapi.service' to reload python-openbmclapi configuration
  Use 'journalctl -f --output cat -u python-openbmclapi.service' to watch the python-openbmclapi logs
"
