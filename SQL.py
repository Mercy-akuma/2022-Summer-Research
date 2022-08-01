import re

import pickle
import datetime
import math
import os
import numpy as np
import pandas as pd
from django import db
from matplotlib.pyplot import table
import dataset as da
def parse_sql_statements(sql_statement : str):
    rule_projections = r'select(.*?)from'
    projection_flag = 0
    projections = re.findall(rule_projections, sql_statement)
    projections = projections[0]
    projections = projections.replace(' ', '') # remove blank spaces
    projections_attributes = projections.split(',')
    # check whether there is DISTINCT condition
    if 'distinct' in projections_attributes[0]:
        projection_flag = 1
    split_point = len(projections_attributes)

    if 'where' in sql_statement:
        rule_projections = r'from(.*?)where'
    else:
        rule_projections = r'(?<=from).*$'
    table_list = re.findall(rule_projections, sql_statement)
    table_list = table_list[0].replace(' ','').split(',')
    table_id = [str(i) + '.id0' for i in table_list ]

    new_sql_statement = sql_statement.replace('distinct ', '')
    location = new_sql_statement.index("from") - 1
    str_list = list(new_sql_statement)
    str_list.insert(location, ', '+', '.join(table_id) )
    new_sql_statement = ''.join(str_list)
    return table_list,split_point,projection_flag, new_sql_statement, projections_attributes

def lineage_on_selections_and_joins(new_sql_statement : str, db, split_point, attr, table_list):
    whole_results = da.select(new_sql_statement, db = db)
    lineage_set = []
    temp = []
    result = []
    for each_data in whole_results:
        table_id = []
        if (None not in each_data.values()):
            for key, value in each_data.items():
                table_id.append(value)
            temp.append(table_id)
            lineage_set.append(table_id[split_point:])
            result.append(table_id[:split_point])
    whole_results = temp
    return lineage_set,  result, whole_results, attr, table_list

def lineage_on_projections(new_sql_statement : str, db, split_point, attr, table_list):
    whole_results = da.select(new_sql_statement, db = db)
    temp = []
    result = []
    for each_data in whole_results:
        table_id = []
        if (None not in each_data.values()):
            for key, value in each_data.items():
                table_id.append(value)
            temp.append(table_id)
    whole_results = temp 
    whole_results.sort()
    # loop each data in the sorted whole_results and obtain the projection lineages
    last_data = []
    current_data = []
    projection_lineage_set = []
    for each_data in whole_results:
        # distinct attributes
        current_data = each_data[ : split_point]
        if(current_data == last_data):
            # projection_lineage_set[projection_num].append(each_data[split_point:]) # the table ids
            # result[projection_num].append(each_data[: split_point]) # value
            continue
        else:
            projection_lineage_set.append(each_data[split_point:]) # the table ids
            result.append(each_data[: split_point]) # value
        last_data = current_data
    return projection_lineage_set, result, whole_results, attr, table_list

def cal_uca_price(no_duplicate_lineage_set : list, table_list:list, db):

    price = 0
    certain_lineage_num = 0
    total_completeness = 0
    base_price_list = []
    for i in range(len(table_list)):
        sum = 0
        base_price = da.select("select BasePrice from Dataset where Name = '%s'"%table_list[i], 'transaction')
        base_price = float(base_price[0]["BasePrice"])
        base_price_list.append(base_price)
        # -2是因为减去id0和empty_num这两个原来不存在在数据里的值
        attribute_num = da.select("SELECT COUNT(*) FROM information_schema. COLUMNS WHERE table_schema = '%s' AND table_name = '%s'"%(db,table_list[i]),db)
        attribute_num = attribute_num[0]['COUNT(*)'] - 2
        for j in range(len(no_duplicate_lineage_set)):
            empty_field_num = da.select("SELECT empty_num from %s where id0 = %d"%(table_list[i], no_duplicate_lineage_set[j][i]) ,db)
            sum += empty_field_num[0]['empty_num']
        attribute_num *= len(no_duplicate_lineage_set)
        total_completeness += 1 - sum / attribute_num
        price += base_price * total_completeness * len(no_duplicate_lineage_set)
        certain_lineage_num += len(no_duplicate_lineage_set)

    return  round(price,3), certain_lineage_num, round(total_completeness,3), base_price_list

def cal_quca_price(no_duplicate_lineage_set : list, table_list:list, attributes_list, sensitivity: float, price_coefficient: float, result_num: int, db): 
    # result_num 是whole_results的大小, 即len(whole_results)
    uca_price,certain_lineage_num,total_completeness,base_price_list = cal_uca_price(no_duplicate_lineage_set, table_list, db)
    # 计算查询质量，需要计算在attribute_list上为空的元素
    uncertain_tuple_num = 0
    uncertain_quality = 0
    for i in range(len(attributes_list)):
        table_name = table_list[i]
        is_null_sql = f''
        for j in range(len((attributes_list[i]))):
            is_null_sql += f'isnull({attributes_list[i][j]})+'			
        is_null_sql=is_null_sql.strip('+') #去掉最后一个加号
        search_sql = f"Select {is_null_sql} from {table_name} where {is_null_sql}<>0"
        results  = da.select(search_sql, db)
        null_list = []
        for each_null in results:
            for _ , k in each_null.items():
                null_list.append(k) 
        uncertain_tuple_num += len(results)
        uncertain_quality += sum([math.pow(sensitivity, null_list[k]) for k in range(len(null_list))]) #注意sensitivity必须在(0, 1)之间，不然uncertain_quality>1
    total_num = uncertain_tuple_num+certain_lineage_num
    total_quality = uncertain_quality + certain_lineage_num
    query_quality = total_quality/total_num #必然在[0, 1]之间，不然是错的
    quca_price = uca_price * query_quality * price_coefficient / result_num
    return uca_price, certain_lineage_num, total_completeness, base_price_list, round(query_quality,3), round(quca_price,3)

def get_lineage(sql_statement : str, db):
    table_list,split_point,projection_flag, new_sql_statement, attr = parse_sql_statements(sql_statement)
    if projection_flag == 0:
        return lineage_on_selections_and_joins(new_sql_statement, db, split_point, attr, table_list)
    else:
        return lineage_on_projections(new_sql_statement, db, split_point, attr, table_list)

def get_attributes_list(projections_attributes, table_list, db):
    ans_list = []
    iter_num = 0
    for i in range(len(table_list)):
        ans_list.append([])
    for table_name in table_list:  
        attributes_list = da.select("desc %s"%table_name, db)
        attr_list = []
        for each_dict in attributes_list:
            attr_list.append(each_dict['Field'])
        for each_attr in projections_attributes:
            if each_attr in attr_list:
                ans_list[iter_num].append(each_attr)
            if '.' in each_attr and iter_num == 0:
                temp_str = each_attr.split('.')
                ans_list[table_list.index(temp_str[0])].append(temp_str[1])
        iter_num += 1
    return ans_list

def check_price(buyer_sql, owner):
    para=da.select("SELECT PriceStrategy, Pricecoefficient, Sensitivity From Dataset where Owner = \'%s\'"% owner, 'transaction')
    coefficient = float(para[0]['Pricecoefficient'])
    sensitivity = float(para[0]['Sensitivity'])
    strategy = para[0]['PriceStrategy']
    no_duplicate_lineage_set,result, whole_results, projections_attributes, table_list= get_lineage(buyer_sql, owner)
    attributes_list = get_attributes_list(projections_attributes, table_list, owner)
    # if strategy == "UCA":
    #     return cal_uca_price(no_duplicate_lineage_set, table_list, owner)
    # if strategy == "QUCA":
    return list(cal_quca_price(no_duplicate_lineage_set, table_list, attributes_list, sensitivity, coefficient, len(whole_results), owner)) + [coefficient, sensitivity, strategy]

if __name__ == "__main__":
    buyer_sql = "select price, cartel from data4 where  0.2 < price  < 0.35 "
    # table_list = parse_sql_statements(buyer_sql)[0]
    # no_duplicate_lineage_set,result, whole_results= get_lineage(buyer_sql, 'yrq')
    # print(cal_uca_price(no_duplicate_lineage_set, table_list, 'yrq'))
    # table_list,split_point,projection_flag, new_sql_statement, projection_attributes = parse_sql_statements(buyer_sql)
    # print(get_attributes('data2','yrq'))
    # print(projection_attributes)
    # print(get_attributes_list(projection_attributes,table_list, 'yrq'))
    # attributes_list = get_attributes_list(projection_attributes, table_list, 'yrq')
    # print(cal_quca_price(no_duplicate_lineage_set, table_list, attributes_list, 0.5, 1, len(whole_results), 'yrq'))
    # print(len(whole_results),len(no_duplicate_lineage_set))
    # print(check_price(buyer_sql,'yrq')) ## 返回9个值，1-4为UCA，5-6为QUCA，7-9为系数
    # a,b,c =[1,2,3]
    print(check_price('select bedrooms, quantity from Data1, Data2 where Data1.id = Data2.id','yrq'))