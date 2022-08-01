import pymysql
import pandas as pd
import os
import numpy as np

host = "127.0.0.1"
port = 3306
user='root'
pwd='root'
charset='utf8'
database='transaction'

def register(Name, Password, Role):
    global host, port, user, pwd, charset, database
    # connect to mysql transaction database
    conn = pymysql.connect(host=host, port=port,user=user,passwd=pwd,charset=charset, db=database)
    cursor = conn.cursor(cursor=pymysql.cursors.DictCursor)

    # add data
    sql = "insert into User(Name,Password,Role) value(%s,%s,%s)"
    cursor.execute(sql,[Name, Password, Role])
    conn.commit()

    # close mysql
    cursor.close()
    conn.close()

def select(sql,db):  # 查询传入sql语句，返回result结果
    global host, port, user, pwd, charset
    conn = pymysql.connect(host=host, port=port,user=user,passwd=pwd,charset=charset, db=db)
    cursor = conn.cursor(cursor=pymysql.cursors.DictCursor)

    # noinspection PyBroadException
    try:
        cursor.execute(sql)
        results = cursor.fetchall()
        return results
    except Exception as e:
        raise e
    finally:
        cursor.close()
        conn.close()

def edit(sql, db):
    global host, port, user, pwd, charset
    # connect to mysql transaction database
    conn = pymysql.connect(host=host, port=port,user=user,passwd=pwd,charset=charset, db=db)
    cursor = conn.cursor(cursor=pymysql.cursors.DictCursor)

    # add data
    cursor.execute(sql)
    conn.commit()

    # close mysql
    cursor.close()
    conn.close()

def read_csv(filename,owner):
    #读取csv文件数据
    csv_name= os.path.dirname(__file__)+'/upload' '/%s/'%owner + filename + ".csv"
    data = pd.read_csv(csv_name, encoding="utf-8")
    data = data.replace(np.NaN, None)
    return data

# def db_completeness(db_name, table_name):
#     sql="SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = "+ "\'%s\'"%db_name+ "AND TABLE_NAME = " + "\'%s\'"%table_name
#     feature= select(sql,"transaction")[1:]
#     search_sql = "SELECT * FROM %s where "%table_name
#     for col in feature:
#         search_sql += "%s IS NOT NULL AND "%col["COLUMN_NAME"]
#     search_sql = search_sql[:-4]
#     data = select(search_sql, db_name)
    
#     return len(data)

def cal_complete(data):
    orig_len = len(data)
    for i in data:
        for j in i.values():
            if j == None:
                orig_len -= 1
                break
    return orig_len




# 将“\upload”中的filename.csv导入dataset这个数据库里建一个新表
def write_data(owner,dname):
    global host, port, user, pwd, charset

    # 首先创造一个owner命名的database
    # 创建连接
    conn = pymysql.connect(host=host, port=port,user=user,passwd=pwd,charset=charset)
    # 创建游标
    cursor = conn.cursor()
    # 创建数据库的sql(如果数据库存在就不创建，防止异常)
    sql = "CREATE DATABASE IF NOT EXISTS %s"%owner 
    # 执行创建数据库的sql
    cursor.execute(sql)
    conn.commit()
    cursor.close()
    conn.close()



    #使用owner的database来写入数据。
    # connect to mysql transaction database
    conn = pymysql.connect(host=host, port=port,user=user,passwd=pwd,charset=charset, db=owner)
    cursor = conn.cursor(cursor=pymysql.cursors.DictCursor)
    #获取数据框的标题行（即字段名称）,将来作为sql语句中的字段名称。
    f = read_csv(dname,owner)
    rows_null = f.isnull().sum(axis=1) 
    f['empty_num'] = rows_null 
    columns = f.columns.tolist()
    # print(columns)
    
    # 将csv文件中的字段类型转换成mysql中的字段类型
    # types = f.dtypes
    field = [] #用来接收字段名称的列表
    table = [] #用来接收字段名称和字段类型的列表
    for item in columns:
        if 'int' in str(f[item].dtype):
            char = item + ' INT'
        elif 'float' in str(f[item].dtype):
            char = item +' FLOAT'
        elif 'object' in str(f[item].dtype):
            char = item +' VARCHAR(255)'
        elif 'datetime' in str(f[item].dtype):
            char = item + ' DATETIME'
        else:
            char = item + ' VARCHAR(255)'
        table.append(char)
        field.append(item)
    # 将table列表中的元素用逗号连接起来，组成table_sql语句中的字段名称和字段类型片段，用来创建表。
    tables = ','.join(table)
    fields = ','.join(field) 

    #如果数据库表已经存在，首先删除它
    cursor.execute('drop table if exists {};'.format(dname))
    conn.commit()
    # print(tables);

    # 构建创建表的SQL语句
    table_sql = 'CREATE TABLE IF NOT EXISTS ' + dname + '(' + 'id0 int PRIMARY KEY NOT NULL auto_increment,' + tables + ');'
    # print('table_sql is: ' + table_sql)

    # 开始创建数据库表
    cursor.execute(table_sql)
    conn.commit()

    # 将数据框的数据读入列表。每行数据是一个列表，所有数据组成一个大列表。也就是列表中的列表，将来可以批量插入数据库表中。
    values = f.values.tolist() #所有的数据
    # print(values)

    # 计算数据框中总共有多少个字段，每个字段用一个 %s 替代。
    s = ','.join(['%s' for _ in range(len(f.columns))])
    # print("s is ",s)

    # 构建插入数据的SQL语句
    insert_sql = 'insert into {}({}) values({})'.format(dname,fields,s)
    # print('insert_sql is:' + insert_sql)

    # 开始插入数据
    cursor.executemany(insert_sql, values) #使用 executemany批量插入数据
    conn.commit()

    # close mysql
    cursor.close()
    conn.close()

    # 返回写入数据个数
    return int(f.shape[0])

