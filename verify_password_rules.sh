#!/bin/bash

# 密码规则对齐验证脚本

echo "=========================================="
echo "  密码规则对齐验证"
echo "=========================================="
echo ""

echo "1️⃣  检查后端密码规则..."
cd api
BACKEND_PATTERN=$(python3 -c "
import sys
sys.path.insert(0, '.')
from pkg.password import password_pattern
print(password_pattern)
")
echo "   后端规则: $BACKEND_PATTERN"
cd ..

echo ""
echo "2️⃣  检查前端密码规则..."
FRONTEND_PATTERN=$(grep "const passwordRegex" ui/src/views/auth/components/LoginForm.vue | sed -n 's/.*\/\^\(.*\)\$\/.*/^\1$/p')
echo "   前端规则: $FRONTEND_PATTERN"

echo ""
echo "3️⃣  对比结果..."
if [ "$BACKEND_PATTERN" = "$FRONTEND_PATTERN" ]; then
    echo "   ✅ 前后端密码规则完全一致!"
else
    echo "   ❌ 前后端密码规则不一致!"
    echo "   后端: $BACKEND_PATTERN"
    echo "   前端: $FRONTEND_PATTERN"
    exit 1
fi

echo ""
echo "4️⃣  测试常见密码..."
python3 - <<'PY'
import re
import sys

pattern = r"^(?=.*[a-zA-Z])(?=.*\d).{8,16}$"
cases = [
    ("abc12345", True),
    ("Abc123456", True),
    ("Pass123!", True),
    ("abcdefgh", False),
    ("12345678", False),
    ("abc123", False),
    ("abcdefgh123456789", False),
]

all_passed = True
for password, expected in cases:
    actual = bool(re.match(pattern, password))
    status = "✅" if actual == expected else "❌"
    print(f"   {status} {password:20s} => {'通过' if actual else '拒绝'} (预期: {'通过' if expected else '拒绝'})")
    if actual != expected:
        all_passed = False

if not all_passed:
    sys.exit(1)
PY

echo ""
echo "=========================================="
echo "  ✅ 验证完成!"
echo "=========================================="
echo ""
echo "📝 密码规则说明:"
echo "  - 至少一个字母(大小写均可)"
echo "  - 至少一个数字"
echo "  - 长度8-16位"
echo "  - 可包含特殊字符(!@#$%等)"
echo ""
