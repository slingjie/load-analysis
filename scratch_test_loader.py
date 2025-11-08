# -*- coding: utf-8 -*-
"""
临时脚本：本地验证 loader.load_dataframe 对中文“月/日”日期+时间的解析。
运行方式：python scratch_test_loader.py
"""
from pathlib import Path
from backend.services import loader

def main() -> None:
    p = Path('负荷测试数据/浙江三中粮油1.csv')
    bs = p.read_bytes()
    print('bytes:', len(bs))
    df = loader.load_dataframe(bs)
    print('df shape:', df.shape)
    print(df.head(10))

if __name__ == '__main__':
    main()

