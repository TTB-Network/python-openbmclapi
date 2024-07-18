# 贡献准则

在为 python-openbmclapi 贡献一份自己的力量前，请先阅读并遵守以下贡献准则。

- [贡献者公约](#贡献者公约)
- [语义化版本](#语义化版本)
- [约定式提交](#约定式提交)
- [基本撰写规则](#基本撰写规则)

## 贡献者公约

为了使 python-openbmclapi 更具有开放性和包容性，请阅读并遵守[贡献者公约](./CODE_OF_CONDUCT.md)。

## 语义化版本

为了规范版本号命名，我们使用了[语义化版本](https://semver.org/lang/zh-CN/)。

版本格式：主版本号.次版本号.修订号，版本号递增规则如下：

1. 主版本号：当你做了不兼容的 API 修改，
2. 次版本号：当你做了向下兼容的功能性新增，
3. 修订号：当你做了向下兼容的问题修正。
   先行版本号及版本编译信息可以加到“主版本号.次版本号.修订号”的后面，作为延伸。

根据此规则，每更新一次版本，只需要更改仓库里面的 `VERSION` 文件出发工作流（Workflow）即可完成一次新版本的发布。

## 约定式提交

为了使每一次提交（commit）更具有规范性，以及为了在发布新版本时更方便地使用 [changelogithub](https://github.com/antfu/changelogithub) 自动化生成发行说明（CHANGELOG），我们使用了[约定式提交](https://www.conventionalcommits.org/zh-hans/v1.0.0/)来规范每一次的提交信息。

### 概述

约定式提交规范是一种基于提交信息的轻量级约定。
它提供了一组简单规则来创建清晰的提交历史；
这更有利于编写自动化工具。
通过在提交信息中描述功能、修复和破坏性变更，
使这种惯例与[语义化版本](http://semver.org/lang/zh-CN)相互对应。

提交说明的结构如下所示：

---

原文：

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

译文：

```
<类型>[可选 范围]: <描述>

[可选 正文]

[可选 脚注]
```

---

<br />
提交说明包含了下面的结构化元素，以向类库使用者表明其意图：

1. **fix:** _类型_ 为 `fix` 的提交表示在代码库中修复了一个 bug（这和语义化版本中的 [`PATCH`](https://semver.org/lang/zh-CN/#%E6%91%98%E8%A6%81) 相对应）。
2. **feat:** _类型_ 为 `feat` 的提交表示在代码库中新增了一个功能（这和语义化版本中的 [`MINOR`](https://semver.org/lang/zh-CN/#%E6%91%98%E8%A6%81) 相对应）。
3. **BREAKING CHANGE:** 在脚注中包含 `BREAKING CHANGE:` 或 <类型>(范围) 后面有一个 `!` 的提交，表示引入了破坏性 API 变更（这和语义化版本中的 [`MAJOR`](https://semver.org/lang/zh-CN/#%E6%91%98%E8%A6%81) 相对应）。
   破坏性变更可以是任意 _类型_ 提交的一部分。
4. 除 `fix:` 和 `feat:` 之外，也可以使用其它提交 _类型_ ，例如 [@commitlint/config-conventional](https://github.com/conventional-changelog/commitlint/tree/master/%40commitlint/config-conventional)（基于 [Angular 约定](https://github.com/angular/angular/blob/22b96b9/CONTRIBUTING.md#-commit-message-guidelines)）中推荐的 `build:`、`chore:`、
   `ci:`、`docs:`、`style:`、`refactor:`、`perf:`、`test:`，等等。
   - build: 用于修改项目构建系统，例如修改依赖库、外部接口或者升级 Node 版本等；
   - chore: 用于对非业务性代码进行修改，例如修改构建流程或者工具配置等；
   - ci: 用于修改持续集成流程，例如修改 Travis、Jenkins 等工作流配置；
   - docs: 用于修改文档，例如修改 README 文件、API 文档等；
   - style: 用于修改代码的样式，例如调整缩进、空格、空行等；
   - refactor: 用于重构代码，例如修改代码结构、变量名、函数名等但不修改功能逻辑；
   - perf: 用于优化性能，例如提升代码的性能、减少内存占用等；
   - test: 用于修改测试用例，例如添加、删除、修改代码的测试用例等。
5. 脚注中除了 `BREAKING CHANGE: <description>` ，其它条目应该采用类似
   [git trailer format](https://git-scm.com/docs/git-interpret-trailers) 这样的惯例。

其它提交类型在约定式提交规范中并没有强制限制，并且在语义化版本中没有隐式影响（除非它们包含 BREAKING CHANGE）。 <br /><br />
可以为提交类型添加一个围在圆括号内的范围，以为其提供额外的上下文信息。例如 `feat(parser): adds ability to parse arrays.`。

### 示例

#### 包含了描述并且脚注中有破坏性变更的提交说明

```
feat: allow provided config object to extend other configs

BREAKING CHANGE: `extends` key in config file is now used for extending other config files
```

#### 包含了 `!` 字符以提醒注意破坏性变更的提交说明

```
feat!: send an email to the customer when a product is shipped
```

#### 包含了范围和破坏性变更 `!` 的提交说明

```
feat(api)!: send an email to the customer when a product is shipped
```

#### 包含了 `!` 和 BREAKING CHANGE 脚注的提交说明

```
chore!: drop support for Node 6

BREAKING CHANGE: use JavaScript features not available in Node 6.
```

#### 不包含正文的提交说明

```
docs: correct spelling of CHANGELOG
```

#### 包含范围的提交说明

```
feat(lang): add polish language
```

#### 包含多行正文和多行脚注的提交说明

```
fix: prevent racing of requests

Introduce a request id and a reference to latest request. Dismiss
incoming responses other than from latest request.

Remove timeouts which were used to mitigate the racing issue but are
obsolete now.

Reviewed-by: Z
Refs: #123
```

## 基本撰写规则

无论是在编写文档、编写程序日志信息以及在 GitHub 上发布 Issue 或者 Pull Request 信息时，请遵循以下规则。

> 本文部分参照[中文文案排版指北](https://github.com/sparanoid/chinese-copywriting-guidelines)，内容可能有出入。

### 概述

撰写规则可以具体概括为：半角符号和全角符号（标点除外）之间用空格隔开，正确使用对应语言的标点符号
和用词习惯。

### 空格

#### 中英文之间需要增加空格

正确：

> 在 IBM 的研究中，他们利用 AI 技术开发了一种先进的语音识别系统。

错误：

> 在IBM的研究中，他们利用AI技术开发了一种先进的语音识别系统。

例外：专有名词、商品名等词语，按照约定俗成的格式书写。

#### 中文与数字之间需要增加空格

正确：

> 今年的全球汽车销售量达到了 8000 万辆。

错误：

> 今年的全球汽车销售量达到了8000万辆。

#### 中文与半角符号之间需要增加空格

正确：

> 很多人都在学习 C++ 这门语言。

错误：

> 很多人都在学习C++这门语言。

#### 数字与单位之间不加空格

正确：

> 我家的光纤入户宽带有 10Gbps，SSD 一共有 10TB。
>
> 这个城市每年平均降雨量为 1200mm。
>
> 角度为 90° 的角，就是直角。

错误：

> 我家的光纤入户宽带有 10 Gbps，SSD 一共有 20 TB。
>
> 这个城市每年平均降雨量为 1200 mm。
>
> 角度为 90 ° 的角，就是直角。

#### 变量与中文之间需要增加空格

变量的输入一般为英文或数字，故变量与中文之间须加入空格。

正确：

> 你扔了一块石头，漂了 ${count} 下。

错误：

> 你扔了一块石头，漂了${count}下。

例外：如果变量的输入确保为中文，则可以不加空格。

#### 全角标点与其他字符之间不加空格

正确：

> 刚刚买了一部 iPhone，好开心！

错误：

> 刚刚买了一部 iPhone ，好开心！

#### 半角标点相关的空格

在半角标点（左引号、左括号等引用标点除外）之后如果有其他字符，请增加空格隔开。

左引号、左括号等引用标点如果其之前有其他字符，请增加空格隔开。

撇号和连接号（hyphen）前后不加空格。破折号（dash）前后需增加空格。

多个半角标点连在一起需看成一个标点，不要用空格将它们分开。

正确：

> The sun set over the horizon, casting a warm glow on the city. As night fell, the lights began to twinkle, creating a captivating skyline.
>
> The storm — with its strong winds, torrential rain, and relentless thunder — lasted for hours, leaving behind a trail of destruction.
>
> The mysterious treasure was said to be hidden deep within the ancient cavern... guarded by mythical creatures and protected by an ancient spell.
>
> "Life is what happens when you're busy making other plans." people always said.
>
> I went to the bookstore yesterday and bought a new novel (the one I've been wanting to read for months).

错误：

> The sun set over the horizon,casting a warm glow on the city.As night fell,the lights began to twinkle,creating a captivating skyline.
>
> The storm—with its strong winds,torrential rain,and relentless thunder—lasted for hours,leaving behind a trail of destruction.
>
> The mysterious treasure was said to be hidden deep within the ancient cavern . . . guarded by mythical creatures and protected by an ancient spell.
>
> " Life is what happens when you' re busy making other plans. " people always said.
>
> I went to the bookstore yesterday and bought a new novel( the one I' ve been wanting to read for months) .

#### 字符串开头和结尾不应出现空白字符

正确：

> 这是一行文字。

错误：

> 这是一行文字。

例外：英文句子的结尾可不遵守此标准。（在字符串需要拼接的情况下，英文句号后的空格是必要的。）

#### 除特殊情况外，不应有多个空格连续出现

正确：

> 我喜欢 GitHub。

错误：

> 我喜欢  GitHub。

### 标点符号

#### 不要连用标点符号

虽然连用标点符号在规范中是被允许的行为，但是这样会破坏句子的规范性和美观性，请不要这样做。

正确：

> 德国队竟然战胜了巴西队！

错误：

> 德国队竟然战胜了巴西队！！！

例外：在表达同时包含疑惑和感叹的语气时，可连用“？！”。

#### 中文使用全角中文标点

正确：

> 嗨！你知道嘛？今天前台的小妹跟我说“喵”了哎！

错误：

> 嗨! 你知道嘛? 今天前台的小妹跟我说 "喵" 了哎!
>
> 嗨!你知道嘛?今天前台的小妹跟我说"喵"了哎!

例外：数学运算符必须使用半角。

#### 简体中文不要使用直角引号

直角引号并不符合简体中文使用者的使用习惯。

正确：

> “老师，‘有条不紊’的‘紊’是什么意思？”

错误：

> 「老师，『有条不紊』的『紊』是什么意思？」

#### 数字和英文使用半角字符

正确：

> 这件蛋糕只卖 200 元。

错误：

> 这件蛋糕只卖 ２００ 元。

#### 引用句内的标点按照其语境使用

引用符号本身仍然需要按照其外部语境决定。

正确：

> 乔布斯那句话是怎么说的？“Stay hungry, stay foolish.”

错误：

> 乔布斯那句话是怎么说的？“Stay hungry，stay foolish。”

#### 英文不要使用弯引号

中文弯引号和英文弯引号属于同一个字符，如果使用弯引号反而会造成阅读问题。请使用直引号 `"`。

正确：

> "Success is not final, failure is not fatal: It is the courage to continue that counts."

错误：

> “Success is not final, failure is not fatal: It is the courage to continue that counts.”

#### 英文省略号使用三个点

原因同上。请使用三个点 `...`。

正确：

> In the serene moonlit night, whispers of ancient tales lingered, echoing through the stillness of time...

错误：

> In the serene moonlit night, whispers of ancient tales lingered, echoing through the stillness of time…

### 语句

#### 使用“你”而不是“您”

用户、开发者与维护者之间互为平级关系，无需使用“您”。

#### 正确使用“的”“地”“得”

示例：

> 他是一个很高的人。
>
> 他总能很快地解决问题。
>
> 他跑得很快。

#### 专有名词使用正确的书写格式

正确：

> 使用 GitHub 登录

错误：

> 使用 Github 登录
>
> 使用 gitHub 登录
>
> 使用 github 登录
>
> 使用 GITHUB 登录

#### 不要使用非正式的缩写

正确：

> 我们需要一位熟悉 JavaScript、HTML5，至少理解一种框架（如 Backbone.js、AngularJS、React 等）的前端开发者。

错误：

> 我们需要一位熟悉 Js、h5，至少理解一种框架（如 backbone、angular、RJS 等）的 FED。
