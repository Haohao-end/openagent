# 使用官方 Node.js 镜像作为基础镜像
FROM node:18-alpine AS builder

# 设置工作目录
WORKDIR /app/web

# 将依赖定义拷贝到镜像内
COPY ui/package*.json ./

# 使用 npm 安装依赖
RUN npm install

# 将项目代码和 api/.env 拷贝到容器中
COPY ui/ ./
COPY api/.env* /app/api/

# Docker 化构建时直接从 api/.env 读取前端 API 前缀
RUN test -f /app/api/.env || (echo "ERROR: missing api/.env. Copy api/.env.example to api/.env and set VITE_API_PREFIX before building." >&2 && exit 1)
RUN VITE_API_PREFIX="$(node ./scripts/read-dotenv-value.mjs /app/api/.env VITE_API_PREFIX)" \
    && export VITE_API_PREFIX \
    && npm run build

# 二阶段使用 Nginx 来部署 Vue 静态页面+
FROM nginx:alpine AS production
COPY --from=builder /app/web/dist /usr/share/nginx/html
COPY --from=builder /app/web/docker/nginx/nginx.conf /etc/nginx/conf.d/default.conf

# 设置目录权限为 755，确保 Nginx 可以访问目录
RUN find /usr/share/nginx/html -type d -exec chmod 755 {} \;

# 设置文件权限为 644，确保文件可以读但不可执行
RUN find /usr/share/nginx/html -type f -exec chmod 644 {} \;

# 暴露 3000 端口号
EXPOSE 3000

# 启动 Nginx
CMD ["nginx", "-g", "daemon off;"]
