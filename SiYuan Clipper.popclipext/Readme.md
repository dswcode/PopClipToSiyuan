# 存入思源 · PopClip 扩展

在任意 App 里选中文字，点一下 PopClip 图标，内容就追加进思源笔记指定的文档。不打开思源、不弹窗、不打断当前操作。

## 工作原理

通过思源 3.7+ 内置的 `SiYuan-Kernel` 命令行直接写 workspace 数据：

```
选中文本 → PopClip → send.py → SiYuan-Kernel block append --parent <文档 ID> --file - → 思源
```

- **不需要 API Token、端口、内核 HTTP 服务**，也不读取 `conf.json`。
- 所有写入都是「追加到文档末尾」，不覆盖、不删除任何已有内容。
- 全程只在本机执行，不联网、不上传数据、不修改剪贴板。
- 已在思源 3.8.8 + PopClip 2026.8.1 + macOS 上验证：CLI 写入后，正在运行的思源内核可立即查到新块。

## 安装

1. 双击 `SiYuan Clipper.popclipext`（或 `SiYuan Clipper.popclipextz`）安装。
2. 首次会弹「未签名扩展」警告，点一次确认即可。想永久免弹，在终端执行一次并重启 PopClip：

   ```bash
   defaults write com.pilotmoon.popclip LoadUnsignedExtensions -bool YES
   ```

3. 需要系统 Python 3（macOS 自带 `/usr/bin/python3`，依赖 Xcode Command Line Tools）。若你的机器上该路径不存在，把 `Config.yaml` 里的 `interpreter` 改成你的 `python3` 绝对路径。

## 关于「安装后文件消失」

PopClip 从 `.popclipextz` 安装成功后**会删除该 zip 文件**，这是它的官方行为，不是文件损坏或误删。为避免交付文件反复消失，本工作区改成这样：

- `SiYuan Clipper.popclipext/` 是源目录，**永远不会被删除**；`Readme.md` 与说明文档都在这里。
- 双击工作区根目录的 **`安装到PopClip.command`** 安装：脚本先把源目录复制成 `/tmp` 下的临时副本再交给 PopClip，被删的只是那个副本。
- `dist/SiYuan Clipper.popclipextz` 是给论坛附件或手动分发用的副本；运行一次上面的脚本即可刷新它。直接双击这个副本也能安装，但它同样会被 PopClip 删掉。
- 旧版 PopClip 把扩展放在 `~/Library/Application Support/PopClip/Extensions/`，新版（2026.8）改存到 `Data/PopClip.sqlite`；在旧目录里找不到本扩展是正常的。

## 首次配置（最少只需一步）

打开 PopClip 设置 → 找到「存入思源」：

- **方式 A（推荐，零配置）**：把「默认定位方式」改成 `今日日记`。装好即用，无需填 ID。
- **方式 B**：保持 `文档 ID`，在「默认文档 ID」里填目标文档的块 ID。

获取文档 ID 的两种方式：

- 思源界面：打开目标文档 → 点文档标题左侧的块标 → 复制 → 复制块 ID。
- 命令行（把标题换成你的文档名）：

  ```bash
  /Applications/SiYuan.app/Contents/Resources/kernel/SiYuan-Kernel \
    sql "SELECT id, hpath FROM blocks WHERE type='d' AND content='文档标题' LIMIT 5" \
    -w "/Users/shawn/Documents/siyuan/SiYuan" -f json
  ```

「CLI 路径」和「Workspace 路径」都留空即可自动探测（本机实测 workspace 为 `/Users/shawn/Documents/siyuan/SiYuan`；插件会显式传 `-w`，因为 CLI 默认会猜错到 `~/SiYuan`）。

## 四种目标定位方式

| 方式 | 配置 | 说明 |
|---|---|---|
| 文档 ID | `默认定位方式 = 文档 ID` + `默认文档 ID` | 最快最稳 |
| 笔记本 + 文档标题/路径 | `默认定位方式 = 笔记本+文档标题` + `文档标题或路径` | 用只读 SQL 查文档 ID；建议写全 `笔记本/文档标题` 避免同名歧义 |
| 今日日记 | `默认定位方式 = 今日日记` +（可选）`笔记本名称或 ID` | 调用 `dailynote create`，由思源自己按设置解析日记路径 |
| 多场景 + 修饰键 | `场景配置` | 点按动作时按住 ⌥ / ⌘ / ⌃ / ⇧ 切换目标 |

### 场景配置格式

每行 `修饰键 | 名称 | 目标`，最多 3 行，`#` 开头为注释：

```
⌥ | 读书摘录 | id:20210808180117-abc1234
⌘ | 灵感收集 | path:我的笔记本/灵感收集
⌃ | 今日日记 | daily:我的笔记本
```

- 修饰键可写 `⌥ ⌘ ⌃ ⇧` 或 `option command control shift`。
- 目标可写 `id:文档ID`、`path:笔记本/文档标题`、`daily:笔记本名`（`daily` 后用默认笔记本）。
- 不按修饰键时使用「默认目标」；同时按下多个键时按场景配置顺序取第一个匹配的。

## 写入内容长什么样

选中的内容作为**一个无序列表项**，来源是它下面缩进的**子列表项**：

```markdown
- 地方政府不只是"守夜人"，而是深度参与经济发展的"运动员"。
  - 15:32 · [置身事内 - 读书笔记](https://example.com/article) · Safari
```

- 正文按纯文本写入，原文里的 Markdown 标记会被转义，避免被思源误解析成格式；来源行的链接仍可点击。
- **PDF 来源**（预览、PDF Expert、Acrobat、Zotero、网址含 `.pdf`，或文字呈现典型 PDF 硬断行）：复制带来的硬换行会智能合并成连续一句——中文直接连接、英文补一个空格、行尾连字符还原断词、空行变一个空格。
- 「识别 PDF 式断行」默认开启：即使认不出应用和网址（例如 Edge 内置 PDF 查看器），只要文字是多行、每行较短、句子被从中间截断，且没有空行、列表或链接，也会自动合并。网页诗歌或窄栏排版若被误合并，关掉此项即可。
- **网页等其他来源**：保留原有分行，但用行内换行留在**同一个列表项块**内，不会散成多个段落。
- 浏览器里选中：来源带网页标题和可点链接；非浏览器 App（PDF、微信、Pages 等）自动降级为 `15:32 · 预览`，不产生空链接。
- 「保留来源信息」关掉后只有正文列表项；「时间格式」可选 `15:32` / `2026-11-04 15:32` / 不显示。
- 若某个 PDF 阅读器没被识别出来，可在「PDF 应用白名单」加一行 App 名关键词，或临时打开「总是合并换行」。

## 反馈与排错

| 情况 | 表现 |
|---|---|
| 成功 | PopClip 显示对勾；可在设置里开启额外的系统通知 |
| 配置问题（找不到 CLI / workspace / 文档 ID 无效 / 找不到文档） | 抖动 X + 系统通知说明原因，并自动弹出设置面板 |
| 命令失败、超时、内核报错 | 抖动 X + 系统通知说明原因 |
| 详细日志 | `~/Library/Logs/PopClip-Siyuan.log` |

常见故障：

| 提示 | 处理 |
|---|---|
| 找不到思源 CLI | 在「CLI 路径」填 `/Applications/SiYuan.app/Contents/Resources/kernel/SiYuan-Kernel` |
| 无法自动探测 Workspace | 在「Workspace 路径」手动填写（本机为 `/Users/shawn/Documents/siyuan/SiYuan`） |
| 找不到文档 | 检查标题拼写，或写全 `笔记本/文档标题` |
| 匹配到多个同名文档 | 写更完整的路径，或在「笔记本名称或 ID」里限定 |
| Edge 里打开 PDF 却没合并 | 确认「识别 PDF 式断行」已开启；若仍不生效，临时打开「总是合并换行」 |
| 思源命令超时 | 调大「命令超时（秒）」；首次冷启动内核可能较慢 |

## 明确不做

截图 / 图片 / 文件 / OCR · PDF 页码与电子书元数据 · 剪贴板接管 · 撤销上一条（请用思源内 ⌘Z）· 全文搜索与管理笔记 · 同步 · 自定义弹窗 · 任何联网上传。

**已知限制**：CLI 不支持加密笔记本；写入经数据层确认可被运行中的内核立即查到，但思源前端界面是否需要手动刷新，请安装后在你常用的视图里确认一次。

## 文件结构

```
SiYuan Clipper.popclipext/
├── Config.yaml   # 扩展定义与 15 项设置
├── send.py       # 主逻辑（Python 3，无第三方依赖）
└── Readme.md
```
