-- sqls/set_operating.sql

USE Trading_prod;

update channels set Operating = 1 where ID in ( -1001622654998, -1001573131967);
