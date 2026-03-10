import json, os, sys
sys.path.append('local-llm-chat')
from core.processor import LabKnowledgeMatcher

def audit_matcher_efficiency():
    matcher = LabKnowledgeMatcher('desk/literature/publications_index.json')
    
    # 模拟数据产生于 2024 年，但论文 2026 年才发表
    test_operator = "NXY"
    data_year = "2024"
    
    # 目前的 Matcher 逻辑 (精确匹配)
    strict_context = matcher.Get_Research_Context(data_year, test_operator)
    print(f"Strict Match (Year {data_year}): {strict_context}")
    
    # 进化版逻辑：时间窗口匹配 (+3 years lag)
    window_years = [str(int(data_year) + i) for i in range(4)]
    broad_titles = []
    target_author = matcher.operator_map.get(test_operator, test_operator)
    
    for pub in matcher.publications:
        if pub['year'] in window_years and target_author.lower() in pub['authors'].lower():
            broad_titles.append(f"[{pub['year']}] {pub['title']}")
            
    print(f"\nBroad Match (Window {data_year}-{int(data_year)+3}):")
    for t in broad_titles[:5]:
        print(f" - {t}")

if __name__ == '__main__':
    audit_matcher_efficiency()
