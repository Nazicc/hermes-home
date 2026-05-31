---
name: ctf-knowledge
description: CTF知识体系 — ctf-wiki / google-ctf / awesome-ctf 三大项目综合沉淀
category: security
---

---
name: ctf-knowledge
description: CTF知识体系 — ctf-wiki / google-ctf / awesome-ctf 三大项目综合沉淀
triggers:
  - ctf
  - ctf学习
  - pwn
  - reverse
  - crypto
  - web安全
  - ctf工具
---

# CTF知识体系

## 来源
1. **ctf-wiki** (ctf-wiki/ctf-wiki) - 综合CTF知识库，覆盖WEB/PWN/CRYPTO/REVERSE/MISC五大方向
2. **google-ctf** (google/google-ctf) - Google官方CTF比赛题库和基础设施
3. **awesome-ctf** (apsdehal/awesome-ctf) - CTF工具、资源列表

> 研究完成度: 2/3（RsaCtfTool待补充）

## ctf-wiki 知识结构

### WEB安全
- SQL注入、XSS、CSRF、SSRF、文件上传、命令注入
- 框架安全：ThinkPHP、Laravel、Struts2
- API安全、JWT、OAuth

### PWN（二进制漏洞）
- 栈溢出、堆溢出、格式化字符串、UAF
- ROP/JOP链构造
- glibc heap mechanism
- 常用工具：pwntools、gdb-pwndbg、ROPgadget、one_gadget

### CRYPTO（密码学）
- 对称加密（AES/DES）、非对称加密（RSA/ECC）
- 分组模式：ECB/CBC/CTR/GCM
- Hash长度扩展攻击、Padding Oracle
- 常见攻击：Wiener Attack、Coppersmith、Hastad's Broadcast

### REVERSE（逆向工程）
- ELF/PE/Mach-O文件结构
- 静态分析：IDA Pro、Ghidra、Radare2
- 动态调试：gdb、x64dbg
- 混淆与反混淆：UPX脱壳、控制流平坦化

### MISC（杂项）
- 隐写术（LSB、EXIF、PNG结构）
- 流量分析（Wireshark、TCPdump）
- 日志分析、内存取证（Volatility）
- 社会工程学

## awesome-ctf 工具清单

| 类别 | 工具 | 用途 |
|------|------|------|
| 逆向工程 | IDA Pro、Ghidra、Radare2、Cutter | 静态/动态分析 |
| 漏洞利用 | pwntools、Pwndbg、ROPgadget、one_gadget | PWN题开发 |
| 密码学 | RsaCtfTool、Cryptool、CyberChef | RSA/古典密码 |
| Web安全 | Burp Suite、sqlmap、dirb、nikto | Web渗透 |
| 取证 | Wireshark、Volatility、foremost、binwalk | 流量/内存/文件取证 |
| 隐写 | zsteg、steghide、exiftool、pngcheck | 图片隐写 |
| 逆向辅助 | uncompyle、jadx、dotnet reflector | 反编译 |
| 综合 | CTFscoreboard、Magicly | 平台/工具 |

## google-ctf 比赛结构

- **Beginner's Quest**: 入门级题目，适合新手
- **Technical Challenges**: 高级技术挑战
- **Categories**: Web, Reverse, Pwn, Crypto, Misc
- **Infrastructure**: Vulnhub风格靶场，Docker容器化

## RsaCtfTool 研究待补充

**仓库**: https://github.com/Ganapati/RsaCtfTool
**用途**: RSA密码攻击工具集
**待研究内容**:
- 功能模块列表和使用方法
- 典型攻击场景（低e、高d、共有因子、Coppersmith等）
- 在CTF crypto题目中的实战用法

> 💡 **补充建议**: 使用 `github-repo-exploration` skill 克隆并分析 RsaCtfTool 源码，重点关注 `attacks/` 目录下的各类攻击实现。
