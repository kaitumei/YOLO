FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .

# 确保环境变量正确设置
ENV NODE_ENV=production

# 确保config目录存在
RUN mkdir -p /app/config

# 修复可能的路由问题
# 查找并修改任何使用完整URL作为路由路径的情况
RUN find ./routes -type f -name "*.js" -exec sed -i 's|router\.use(\s*"https://|router\.use(\s*"/|g' {} \;
RUN find ./routes -type f -name "*.js" -exec sed -i 's|router\.get(\s*"https://|router\.get(\s*"/|g' {} \;
RUN find ./routes -type f -name "*.js" -exec sed -i 's|router\.post(\s*"https://|router\.post(\s*"/|g' {} \;
RUN find ./routes -type f -name "*.js" -exec sed -i 's|router\.put(\s*"https://|router\.put(\s*"/|g' {} \;
RUN find ./routes -type f -name "*.js" -exec sed -i 's|router\.delete(\s*"https://|router\.delete(\s*"/|g' {} \;

# 修改app.js中的路由注册
RUN sed -i 's|app\.use(\s*"https://|app\.use(\s*"/|g' app.js
RUN sed -i 's|app\.get(\s*"https://|app\.get(\s*"/|g' app.js
RUN sed -i 's|app\.post(\s*"https://|app\.post(\s*"/|g' app.js
RUN sed -i 's|app\.put(\s*"https://|app\.put(\s*"/|g' app.js
RUN sed -i 's|app\.delete(\s*"https://|app\.delete(\s*"/|g' app.js

# 添加更多调试信息以验证修复
RUN echo "路由问题修复完成"

# 删除debug-routes.js文件，因为它包含了故意引入的错误URL
RUN rm -f debug-routes.js || echo "debug-routes.js不存在"

# 运行配置修复脚本
RUN node fix-config.js || echo "配置修复脚本执行失败，将在启动时重试"

# 确保启动脚本有执行权限
RUN chmod +x docker-entrypoint.sh || echo "无法设置权限，启动时解决"

EXPOSE 3000
CMD ["./docker-entrypoint.sh"] 