#!/bin/bash
# ============================================
# 生成自签名 SSL 证书（仅用于开发/测试环境）
# 生产环境请使用 Let's Encrypt 或正式 CA 证书
# ============================================

CERT_DIR="$(dirname "$0")"

# 证书 Subject 字段，支持通过环境变量覆盖；默认使用中立通用占位，避免泄漏个人/公司信息
CERT_COUNTRY="${CERT_COUNTRY:-US}"
CERT_STATE="${CERT_STATE:-CA}"
CERT_LOCALITY="${CERT_LOCALITY:-Local}"
CERT_ORG="${CERT_ORG:-Mem0Dashboard}"
CERT_CN="${CERT_CN:-localhost}"
CERT_DAYS="${CERT_DAYS:-365}"

echo "正在生成自签名 SSL 证书..."
echo "  Subject: /C=${CERT_COUNTRY}/ST=${CERT_STATE}/L=${CERT_LOCALITY}/O=${CERT_ORG}/CN=${CERT_CN}"
openssl req -x509 -nodes -days "${CERT_DAYS}" \
    -newkey rsa:2048 \
    -keyout "${CERT_DIR}/key.pem" \
    -out "${CERT_DIR}/cert.pem" \
    -subj "/C=${CERT_COUNTRY}/ST=${CERT_STATE}/L=${CERT_LOCALITY}/O=${CERT_ORG}/CN=${CERT_CN}"

echo "证书已生成："
echo "  证书文件: ${CERT_DIR}/cert.pem"
echo "  私钥文件: ${CERT_DIR}/key.pem"
echo ""
echo "⚠️  这是自签名证书，仅用于开发/测试环境。"
echo "   生产环境请使用 Let's Encrypt 或正式 CA 签发的证书。"
