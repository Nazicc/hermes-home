# 应用安全自免疫平台（RASP）

## 产品概述

天融信应用安全自免疫平台（RASP - Runtime Application Self-Protection）是天融信面向云原生和微服务架构下的应用运行时安全防护产品。RASP 通过 Java Agent / .NET Profiler / PHP Extension / Node.js Hook 等技术将安全引擎注入到应用运行时环境中，在应用内部实时监控所有函数调用、数据库操作、文件读写、网络请求等执行上下文，实现应用层的"自体免疫"——安全能力与应用深度融合，在应用执行阶段精准识别并阻断攻击行为。

与传统的 WAF（外围网络层检测）不同，RASP 运行在应用内部，拥有完整的执行上下文（参数类型、返回值、调用栈、SQL 语句结构等），检测精度极高（低误报率），且无需修改应用代码或调整网络架构。产品特别适用于云原生环境（K8s/容器）中弹性伸缩的应用实例，是 DevSecOps 体系下"安全左移"之后"安全右移"的关键技术手段。

## 核心功能

| 功能模块 | 说明 |
|---------|------|
| **SQL 注入实时防御** | 在 JDBC/MyBatis/Hibernate 等数据库驱动层拦截 SQL 语句，分析 SQL 结构与参数，阻断注入攻击 |
| **命令执行防御** | 监控 Runtime.exec / ProcessBuilder / ProcessImpl 等系统命令执行调用链，检测命令注入 |
| **反序列化攻击防御** | 检测 Java 反序列化（readObject/readUnshared）调用链中的 Gadget Chain 攻击 |
| **文件操作防御** | 监控文件读写（FileInputStream/FileOutputStream/RandomAccessFile）操作，检测目录遍历与任意文件上传 |
| **SSRF 防御** | 监控 HTTP URLConnection / HttpClient 请求中的 URL 参数，检测服务器端请求伪造 |
| **表达式注入防御** | 检测 SpEL / OGNL / MVEL / 脚本引擎等表达式执行中的注入攻击 |
| **内存马检测与清除** | 检测应用 JVM 进程中的内存马（Servlet/Filter/Listener/Agent 型），支持手动和自动清除 |
| **漏洞虚拟补丁** | 对已知高危漏洞（如 Log4Shell/Shiro RCE/Spring4Shell）以热补丁方式在运行时注入防御逻辑 |
| **应用行为基线** | 学习应用正常运行时的函数调用链与资源访问模式，发现偏离基线的异常行为 |
| **IAST 集成** | 与交互式应用安全测试（IAST）工具联动，在测试阶段实时发现漏洞 |

## 技术规格

| 参数 | 指标 |
|------|------|
| 支持语言与框架 | Java（6+/8/11/17/21）、.NET（Framework 4.5+/Core 3.1+/6/8）、PHP（7.4+/8+）、Node.js（14+/18+） |
| Java 框架覆盖 | Spring Boot、Spring Cloud、Tomcat、Jetty、WebLogic、WebSphere、JBoss、Resin、Undertow、Netty |
| 检测引擎 | 字节码插桩 + 污点追踪 + 调用链分析 |
| 性能影响 | P99 响应时间增加 < 5%（基准测试，8 核 16GB JVM） |
| 启动方式 | -javaagent / .NET Profiler / PHP Extension / Node.js --require |
| 部署模式 | 容器 Sidecar / 主机 Agent / 云原生 Operator |
| K8s 集成 | DaemonSet / Sidecar Injector / Admission Controller |
| 虚拟补丁 | 支持自定义漏洞热补丁规则 |
| 日志输出 | 本地文件 / Syslog / ES / Kafka |
| 管理平台 | Web GUI / REST API / 多租户管理 |

## 适用场景

- **云原生/容器化应用安全**：K8s 环境中 Pod 弹性伸缩，传统 WAF 无法覆盖东西向流量和动态端口，RASP 嵌入应用内部提供原生安全防护。
- **0-Day 漏洞应急**：高危漏洞（Log4Shell/SHIRO/Spring4Shell）爆发时，WAF 规则需要数小时到数天才能生效，RASP 的虚拟补丁可在分钟级完成部署阻断攻击。
- **第三方组件漏洞防护**：企业应用依赖大量开源/第三方组件，RASP 可在不升级组件版本的前提下运行时阻断已知漏洞利用。
- **等保2.0 应用安全合规**：满足"应检测应用运行时的安全威胁"、"应提供应用自我防护能力"等要求。
- **DevSecOps 流水线**：CI/CD 流水线中集成 RASP 进行自动化运行时安全测试（结合 IAST），上线后持续运行防护。

## 实战Tips（安服工程师经验）

> **云南区域经验：**
> - 云南省政府/金融客户通常使用较老版本的 Java 应用（Java 6/7 运行的政务审批、社保系统），这些老版本应用无法升级 JDK 且存在大量已知漏洞。RASP 的虚拟补丁是解决此类"不能升级、不能下线"遗留系统安全问题的核心方案——在 JDK 层面注入补丁代码，无需修改应用即可阻断 Log4j/Shiro/反序列化等高危攻击。
> - 云南高校（云南大学/昆明理工/云南财经等）的教务系统/科研管理系统通常采用老旧架构（Struts 2 / Spring MVC + JSP）。如果这些系统运行在 K8s 容器中，建议 RASP 以 DaemonSet 方式部署，自动注入到所有 Java Pod——无需为每个应用单独配置代理。
> - 云南省电子政务内网中部分系统使用 WebLogic/WebSphere 等商用中间件，标准 RASP Agent 需要验证与这些中间件的兼容性。建议先在测试环境运行 RASP 1-2 周，重点观察性能影响和日志量，确认无误后再投入生产。

> **贵州区域经验：**
> - 贵州大数据企业（如贵州数据宝、中电科大数据院）的核心业务由大量微服务组成（Spring Cloud 体系），建议 RASP 通过 Kubernetes Sidecar Injector 自动注入——修改 Pod 的 Annotation 即可完成注入，无需修改 Deployment YAML。推荐配置 `sidecar-injector: enabled=true` 全局启用，对有性能敏感的服务（如高并发 API）单独配置排除。
> - 贵州金融机构（贵州银行/贵阳银行/农信社）的核心业务系统通常部署在物理机/VM 上，RASP 需通过主机 Agent 方式部署。注意多个 Java 应用共享同一个 Tomcat 实例的场景——RASP Agent 只需在 JVM 启动参数中添加一次 `-javaagent`，该 JVM 内的所有 Web 应用都会被统一防护。
> - 贵州"东数西算"节点数据中心内的大量老旧应用（Java 6/7）是 Log4Shell 等漏洞的重灾区。建议分批部署 RASP 虚拟补丁：优先级排序为"暴露于公网的应用 → 内网核心业务系统 → 内部管理系统"，确保有限资源覆盖最高风险。

> **通用经验：**
> - RASP 部署务必遵循"灰度发布"原则：先在 1-2 个非核心应用上部署运行 1 周，观察是否有兼容性问题（Java Agent 与 APM Agent 如 SkyWalking/Pinpoint 的冲突是最常见的问题）和性能影响（CPU/内存/JVM GC 频率），确认无误后再逐步推广到全量应用。强烈不建议一次性全量部署——一旦出现兼容性问题将影响所有业务。
> - Java Agent 的加载顺序会影响 RASP 的检测效果：如果 SkyWalking/Pinpoint 等 APM Agent 在 RASP Agent 之前加载，可能会修改某些类的字节码，导致 RASP 的插桩失效。解决方案：在 `-javaagent` 参数中确保 RASP Agent 排在其他 Agent 之前。
> - RASP 的日志量可能远超预期——在生产环境中，一个中等流量的 Java 应用（100 TPS）每日 RASP 日志可达数 GB。建议配置日志采样策略：对阻断的事件全量记录，对正常检测的请求仅记录日志摘要（丢弃请求体和响应体），并接入 ES/Kafka 做日志分析。
> - 内存马的检测与清除是 RASP 的"杀手级功能"——安全攻防演练中发现内存马通过 RASP 比传统方法早 30 分钟以上。建议在攻防演练期间开启"自动清除"模式，日常运行保持"告警"模式由安全人员确认后再清除，避免误清除正常的动态代理/Filter 导致业务异常。
