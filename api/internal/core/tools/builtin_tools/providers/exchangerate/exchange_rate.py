import json
from typing import Any, Type
import requests
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool
from internal.lib.helper import add_attribute


class ExchangeRateArgsSchema(BaseModel):
    from_currency: str = Field(description="源货币代码，例如：USD（美元）、CNY（人民币）、EUR（欧元）")
    to_currency: str = Field(description="目标货币代码，例如：USD（美元）、CNY（人民币）、EUR（欧元）")
    amount: float = Field(default=1.0, description="需要转换的金额，默认为1")


class ExchangeRateTool(BaseTool):
    """汇率查询和货币转换工具"""
    name: str = "exchange_rate"
    description: str = "查询实时汇率并进行货币转换计算"
    args_schema: Type[BaseModel] = ExchangeRateArgsSchema

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """调用汇率API进行查询"""
        try:
            from_currency = kwargs.get("from_currency", "USD").upper()
            to_currency = kwargs.get("to_currency", "CNY").upper()
            amount = kwargs.get("amount", 1.0)

            # 使用免费的汇率API
            api_url = f"https://api.exchangerate-api.com/v4/latest/{from_currency}"

            response = requests.get(api_url, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "rates" in data and to_currency in data["rates"]:
                rate = data["rates"][to_currency]
                converted_amount = amount * rate
                result = {
                    "from": from_currency,
                    "to": to_currency,
                    "rate": rate,
                    "amount": amount,
                    "converted_amount": round(converted_amount, 2),
                    "date": data.get("date", ""),
                    "result": f"{amount} {from_currency} = {round(converted_amount, 2)} {to_currency}"
                }
                return json.dumps(result, ensure_ascii=False)

            return f"无法获取{from_currency}到{to_currency}的汇率"
        except Exception as e:
            return f"汇率查询失败：{str(e)}"


@add_attribute("args_schema", ExchangeRateArgsSchema)
def exchange_rate(**kwargs) -> BaseTool:
    """获取汇率查询工具"""
    return ExchangeRateTool()
