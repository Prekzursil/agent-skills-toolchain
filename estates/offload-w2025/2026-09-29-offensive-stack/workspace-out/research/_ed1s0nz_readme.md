# SecurityMCP-Hub

构建一个完整的网络安全工具 MCP 服务生态，让大模型能够自主调用各类安全工具，实现智能化的安全测试、资产发现、漏洞扫描等任务。所有服务遵循统一标准，支持完全自主的参数配置，无需人工干预。

## 项目特点

- 🚀 **独立部署**：每个服务可独立编译和运行，互不依赖
- 🔧 **统一接口**：所有服务遵循 MCP 标准协议
- 📦 **易于扩展**：提供模板和脚本，快速创建新服务

## 项目结构

```
SecurityMCP-Hub/
├── README.md                    # 项目主文档
├── servers/                     # 核心目录：所有MCP服务
│   ├── fofa-mcp/               # FOFA服务 ✅
│   ├── zoomeye-mcp/           # ZoomEye服务 ✅
│   ├── sqlmap-mcp/             # SQLMap服务 (计划中)
│   ├── nmap-mcp/               # Nmap服务 (计划中)
│   ├── nuclei-mcp/             # Nuclei服务 (计划中)
│   │   ...                     # 更多服务持续开发中
│   └── template/               # 新服务模板
├── docs/                        # 项目文档
├── scripts/                     # 辅助脚本
│   └── build.sh                # 构建脚本
└── examples/                    # 集成示例
    └── mcp-config.json         # MCP配置示例
```

## 已实现服务

### ✅ fofa-mcp

FOFA 资产搜索服务，支持大模型自主检索和配置。

详细功能和使用方法请查看：[fofa-mcp 文档](./servers/fofa-mcp/README.md)

### ✅ zoomeye-mcp

ZoomEye 资产搜索服务，支持大模型自主检索和配置。

详细功能和使用方法请查看：[zoomeye-mcp 文档](./servers/zoomeye-mcp/README.md)

## 部署方式

所有 MCP 服务采用统一的部署方式：

### 方式一：手动部署

1. 进入对应服务目录
2. 编译项目
3. 配置环境变量
4. 运行服务

示例（以 fofa-mcp 为例）：

```bash
cd servers/fofa-mcp
go build -o fofa-mcp server.go
export FOFA_EMAIL=your_email@example.com
export FOFA_KEY=your_api_key_here
./fofa-mcp
```

### 方式二：使用构建脚本

```bash
# 构建所有服务
./scripts/build.sh

# 然后运行特定服务
cd servers/fofa-mcp
export FOFA_EMAIL=your_email@example.com
export FOFA_KEY=your_api_key_here
./fofa-mcp
```

## MCP 客户端配置

在您的 MCP 客户端配置文件中添加服务配置，参考 `examples/mcp-config.json`：

```json
{
  "mcpServers": {
    "fofa": {
      "command": "/path/to/SecurityMCP-Hub/servers/fofa-mcp/fofa-mcp",
      "env": {
        "FOFA_EMAIL": "your_email@example.com",
        "FOFA_KEY": "your_api_key_here"
      }
    },
    "zoomeye": {
      "command": "/path/to/SecurityMCP-Hub/servers/zoomeye-mcp/zoomeye-mcp",
      "env": {
        "ZOOMEYE_API_KEY": "your_api_key_here"
      }
    }
  }
}
```

## 开发计划

- [x] fofa-mcp - FOFA 资产搜索
- [x] zoomeye-mcp - ZoomEye 资产搜索
- [ ] sqlmap-mcp - SQL 注入检测
- [ ] nmap-mcp - 网络扫描
- [ ] nuclei-mcp - 漏洞扫描

## 新增服务需求

如果您有新增 MCP 服务的需求，请提交 Issue。在 Issue 中请务必包含以下信息：

- **工具名称**：要集成的安全工具名称
- **API 文档**：如果工具提供 OpenAPI/Swagger 文档，请提供 API 地址
- **命令行帮助**：如果工具是命令行工具，请提供 `--help` 或 `-h` 的输出信息
- **使用场景**：简要说明该工具的主要用途和使用场景
- **其他信息**：任何其他有助于理解工具功能的信息

示例 Issue 格式：

```
工具名称：nmap
API 文档：无（命令行工具）
命令行帮助：
$ nmap --help
Nmap 7.94 ( https://nmap.org )
Usage: nmap [Scan Type(s)] [Options] {target specification}
...
使用场景：网络端口扫描、服务识别、漏洞检测
```

## 贡献指南

欢迎贡献新的 MCP 服务！

1. 参考 `servers/template/` 目录中的模板
2. 创建新的服务目录
3. 实现 MCP 协议接口
4. 添加 README 文档
5. 提交 Pull Request

### 服务开发要求

- ✅ 通过 stdio 进行 JSON-RPC 通信
- ✅ 实现 MCP 协议标准
- ✅ 支持环境变量配置
- ✅ 可独立编译和运行
- ✅ 所有参数可自主配置，无硬编码限制

## 许可证

MIT License


