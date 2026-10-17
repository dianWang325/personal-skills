# 维护约定

仅提交可复用的 skill，不提交实验数据、日志、凭据和机器私有配置。修改 skill 时同步维护 SKILL.md、scripts、references 和 agents；验证脚本与 skill 格式，再更新本机安装副本。

每次创建提交前在本仓库设置 `git config user.name dianWang325`、`git config user.email 93850926+dianWang325@users.noreply.github.com`。作者和提交者均使用该身份，执行 `git commit -s`，Signed-off-by 必须为 `dianWang325 <93850926+dianWang325@users.noreply.github.com>`。推送前验证这三项，改写已推送历史先征得用户确认。
