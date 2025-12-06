import re

# 读取文件
with open('./components/StorageCyclesPage.tsx', 'rb') as f:
    raw_bytes = f.read()

content = raw_bytes.decode('utf-8')

# 找到函数开始行（第31行的注释）
lines = content.split('\r\n')

# 找函数起始行
start_line = -1
end_line = -1

for i, line in enumerate(lines):
    if '基于后端返回的日度 cycles' in line and 'computeYearEquivalentCyclesFromDays' not in line:
        start_line = i
        print(f"Function comment at line {i+1}")
    if start_line >= 0 and i > start_line:
        # 找到函数结束的 };（独立的一行只有 };）
        if line.strip() == '};' and i > start_line + 5:
            end_line = i
            print(f"Function ends at line {i+1}")
            break

if start_line >= 0 and end_line > start_line:
    # 新代码（使用 CRLF）
    new_code_lines = [
        '// 基于后端返回的日度 cycles 计算"全年合计等效循环数"',
        '// 修复：使用全年有效天数的日均循环数 × 365，避免整月无数据时漏算',
        'const computeYearEquivalentCyclesFromDays = (',
        "  days: BackendStorageCyclesResponse['days'] | undefined | null,",
        '): number => {',
        '  if (!days || !days.length) return 0;',
        '  ',
        '  const validDaySet = new Set<string>();',
        '  let totalCycles = 0;',
        '',
        '  days.forEach(d => {',
        '    if (!d?.date) return;',
        '    const dateKey = String(d.date);',
        '    const cyclesVal = Number(d.cycles ?? 0);',
        '    if (cyclesVal > 0) {',
        '      validDaySet.add(dateKey);',
        '    }',
        '    totalCycles += cyclesVal;',
        '  });',
        '',
        '  const yearValidDays = validDaySet.size;',
        '  ',
        '  if (yearValidDays > 0) {',
        '    return (totalCycles / yearValidDays) * 365;',
        '  }',
        '  return 0;',
        '};',
    ]
    
    # 替换行
    new_lines = lines[:start_line] + new_code_lines + lines[end_line+1:]
    new_content = '\r\n'.join(new_lines)
    
    with open('./components/StorageCyclesPage.tsx', 'wb') as f:
        f.write(new_content.encode('utf-8'))
    
    print(f"Replaced lines {start_line+1} to {end_line+1} with new code")
    print("Replacement successful!")
else:
    print(f"Could not find function boundaries: start={start_line}, end={end_line}")
