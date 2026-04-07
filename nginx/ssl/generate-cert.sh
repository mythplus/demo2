#!/bin/bash
# ============================================
# 生成自签名 SSL 证书（仅用于开发/测试环境）
# 生产环境请使用 Let's Encrypt 或正式 CA 证书
# ============================================

CERT_DIR="$(dirname "$0")"

echo "正在生成自签名 SSL 证书..."
openssl req -x509 -nodes -days 365 \
    -newkey rsa:2048 \
    -keyout "${CERT_DIR}/key.pem" \
    -out "${CERT_DIR}/cert.pem" \
    -subj "/C=CN/ST=Guangdong/L=Shenzhen/O=Mem0Dashboard/CN=localhost"

echo "证书已生成："
echo "  证书文件: ${CERT_DIR}/cert.pem"
echo "  私钥文件: ${CERT_DIR}/key.pem"
echo ""
echo "⚠️  这是自签名证书，仅用于开发/测试环境。"
echo "   生产环境请使用 Let's Encrypt 或正式 CA 签发的证书。"
