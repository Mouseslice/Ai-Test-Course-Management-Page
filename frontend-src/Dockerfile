# 使用Node.js作为基础镜像来安装Playwright
FROM node:18-alpine

# 使用清华源加速 apk（国内构建稳定性）
RUN sed -i 's|dl-cdn.alpinelinux.org/alpine|mirrors.tuna.tsinghua.edu.cn/alpine|g' /etc/apk/repositories

# 安装必要的依赖
RUN apk add --no-cache \
    chromium \
    nss \
    freetype \
    harfbuzz \
    ca-certificates \
    ttf-freefont \
    nginx

# 安装Playwright（使用国内npm镜像）
RUN npm install -g playwright --registry=https://registry.npmmirror.com

# 设置Playwright使用系统Chromium
ENV PLAYWRIGHT_SKIP_VALIDATE_HOST_REQUIREMENTS=true
ENV PLAYWRIGHT_BROWSERS_PATH=/usr/bin/chromium-browser

# 设置工作目录
WORKDIR /usr/share/nginx/html

# 复制前端文件
COPY ./html .

# 复制教师端构建产物（teacher-dist/ 由构建脚本从 teacher-frontend 构建后拷入，不入 git）
COPY ./teacher-dist /usr/share/nginx/teacher

# 复制Nginx配置文件
COPY ./nginx.conf /etc/nginx/nginx.conf

# 暴露端口（80=学生端，8326=教师端）
EXPOSE 80 8326

# 启动Nginx
CMD ["nginx", "-g", "daemon off;"]
