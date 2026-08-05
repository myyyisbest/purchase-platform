"""
导出服务
生成Excel导出文件
"""
import pandas as pd
from typing import List, Optional
from fastapi.responses import StreamingResponse
import io
from datetime import datetime


class ExportService:
    """导出服务类"""

    def generate_yoy_excel(
        self,
        items: List[dict],
        current_year: int,
        period: int,
        company_name: Optional[str] = None
    ) -> StreamingResponse:
        """
        生成同期对比分析的Excel文件
        
        表头设计（参考 purchase analysis 的双行表头）：
        - 固定列：公司代码、公司名称、物料代码、物料名称
        - 当年累计组：金额(CNY)、数量、平均单价
        - 上年全年组：金额(CNY)、数量、平均单价
        - 同比分析组：单价变动、变动率(%)、成本变动(CNY)
        """
        # 构建DataFrame
        rows = []
        for item in items:
            rows.append({
                '公司代码': item['company_code'],
                '公司名称': item['company_name'],
                '物料代码': item['material_code'],
                '物料名称': item['material_name'],
                f'{current_year}年1-{period}月金额(CNY)': item['current_amount'],
                f'{current_year}年1-{period}月数量': item['current_qty'],
                f'{current_year}年1-{period}月平均单价': item['current_avg_price'],
                f'{current_year-1}年全年金额(CNY)': item['prev_amount'],
                f'{current_year-1}年全年数量': item['prev_qty'],
                f'{current_year-1}年全年平均单价': item['prev_avg_price'],
                '单价变动(CNY)': item['price_change'],
                '变动率(%)': item['price_change_rate'],
                '成本变动(CNY)': item['cost_change'],
            })

        df = pd.DataFrame(rows)

        # 写入Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='同期对比分析')

            # 获取worksheet对象进行样式调整
            ws = writer.sheets['同期对比分析']

            # 列宽设置
            col_widths = {
                'A': 12,  # 公司代码
                'B': 25,  # 公司名称
                'C': 15,  # 物料代码
                'D': 30,  # 物料名称
            }
            for col, width in col_widths.items():
                ws.column_dimensions[col].width = width

        output.seek(0)

        # 生成文件名
        filename = f"采购同期对比分析_{current_year}年1-{period}月vs{current_year-1}年"
        if company_name:
            filename += f"_({company_name})"
        filename += f"_{datetime.now().strftime('%Y%m%d%H%M')}.xlsx"

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    def generate_single_source_risk_excel(
        self,
        items: list,
        fiscal_year: Optional[int] = None
    ) -> StreamingResponse:
        """
        生成单源供应风险清单的Excel文件
        """
        rows = []
        for i, item in enumerate(items, 1):
            rows.append({
                '序号': i,
                '物料编码': item.get('material_code', ''),
                '物料名称': item.get('material_name', ''),
                '唯一供应商': item.get('supplier_name', ''),
                '采购金额(CNY)': item.get('amount_cny', 0),
                '风险等级': '高风险',
            })

        df = pd.DataFrame(rows)

        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='单源供应风险')

            ws = writer.sheets['单源供应风险']
            col_widths = {'A': 8, 'B': 15, 'C': 30, 'D': 30, 'E': 18, 'F': 12}
            for col, width in col_widths.items():
                ws.column_dimensions[col].width = width

        output.seek(0)

        filename = f"单源供应风险清单_{fiscal_year or 'all'}_{datetime.now().strftime('%Y%m%d%H%M')}.xlsx"

        return StreamingResponse(
            output,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )