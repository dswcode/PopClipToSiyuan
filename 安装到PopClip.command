#!/bin/bash
# 把「存入思源」扩展交给 PopClip 安装，工作区里的源文件保持不变。
#
# PopClip 从 .popclipextz 安装成功后会删除该 zip 文件，这是它的官方行为。
# 所以这里先把源目录复制成临时副本，交给 PopClip 的是副本，被删的也是副本。

set -e

HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$HERE/SiYuan Clipper.popclipext"
DIST="$HERE/dist"
ZIPNAME="SiYuan Clipper.popclipextz"

if [ ! -d "$SRC" ]; then
  echo "找不到扩展源目录：$SRC"
  echo "请确认 SiYuan Clipper.popclipext 与本脚本放在同一文件夹。"
  exit 1
fi

mkdir -p "$DIST"
TMP="$(mktemp -d /tmp/popclip-siyuan-XXXXXX)"
cp -R "$SRC" "$TMP/"
(cd "$TMP" && zip -q -r "$ZIPNAME" "SiYuan Clipper.popclipext")
cp "$TMP/$ZIPNAME" "$DIST/$ZIPNAME"

echo "已刷新分发副本：$DIST/$ZIPNAME"
echo "正在把临时副本交给 PopClip 安装…"
echo "（临时副本：$TMP，安装后由 PopClip 自行删除，不影响工作区）"

open -a PopClip "$TMP/$ZIPNAME" 2>/dev/null || open "$TMP/$ZIPNAME"

echo
echo "完成。若弹出「未签名扩展」警告，点确认即可。"
echo "想永久免弹，可在终端执行一次后重启 PopClip："
echo "  defaults write com.pilotmoon.popclip LoadUnsignedExtensions -bool YES"
echo
echo "工作区里的 SiYuan Clipper.popclipext/ 和所有说明文档都保持不变。"
