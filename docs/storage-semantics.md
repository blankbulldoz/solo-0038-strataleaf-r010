# 数据与兼容边界

物理表包括 meta、collections、versions、commits、receipts、index_defs、index_values、text_defs、text_postings、pins、consumers。versions 的主键为集合、键、修订；body 的 SQL NULL 表示删除，JSON null 只能作为文档字段。collections 保存当前模式；index_values 与 text_postings 是当前 head 的投影。commits 保存完整的操作序列；receipts 保存不受历史回收影响的请求摘要与结果。幂等键不能被不同操作复用，回放不重新执行前置条件。

floor 是仍可读取的最早修订，不代表每条物理版本的最小修订；每个键在 floor 之前的最后版本可能是构造 floor 读视图的基准，必须保留。commits 仅需保存大于 floor 的提交，消费者从自己的 ack 之后读取。pin 与消费者位置不能低于现存 floor。

模式包含 fields、required、additional，支持点路径类型；additional=false 限制顶层未知根字段，不递归禁止已声明对象中的子字段。字段不允许 null，除非该字段未声明类型；缺失可通过 required 控制。integer 排除 bool，number 接受整数及有限浮点。JSON 对象不允许非字符串键；浮点必须有限。索引忽略缺失字段与对象/数组，空值作为可索引标量，数值 1 和 1.0 共用索引值，true 与 1 不共用。

全文索引按集合与字段登记在 text_defs，词元倒排保存在 text_postings 并随文档写入同一提交刷新。分词器固定：U+3400–U+4DBF、U+4E00–U+9FFF、U+F900–U+FAFF 的表意字符逐字成词；其余 Unicode 字母或数字的连续段经 casefold 成一个词元；其余字符为分隔符。查询词元去重后按合取匹配，文档侧重复词元只影响 explain 报告的频次。非字符串与缺失字段不进入倒排也不匹配。text_postings 只服务当前 head；历史修订与 force_scan 走版本扫描，最终匹配始终对原文重新分词复核，因此回收版本之后的全文读取按既有 SnapshotTooOld 规则拒绝。

游标携带数据库身份、谓词摘要、读版本和最后键，并由数据库私有密钥签名。它不是权限凭据，不冻结模式，也不是保留租约。需要稳定的长时间读取，调用者自行管理具名保留点。

副本包是内部可信通道数据，校验和只用于检测传输损坏。正常备份恢复新主库保留逻辑内容而更换身份；副本初始化保留上游身份。分段追赶未完成时暂不提供当前索引，避免最新唯一约束错误约束中间历史视图。目录 epoch 可在没有文档提交时前进，最终空提交包仍能传递新的模式与索引。
