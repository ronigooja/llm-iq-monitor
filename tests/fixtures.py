import pytest

from llm_iq_monitor.db import connect


@pytest.fixture
def monitor_db(tmp_path):
    path = tmp_path / "monitor.db"
    db = connect(path)
    db.executescript(
        """
        INSERT INTO models VALUES ('alpha', 1, 1, 100, 100), ('beta', 1, 1, 100, 100);
        INSERT INTO prices VALUES ('alpha', 'openai', 1, 2, 120);
        INSERT INTO runs VALUES (1,'alpha','medium','20261102','v1','schedule','["math","logic","write_zh","write_en"]','{}',1,2,120,90,100,'ok',10,0.1,2,NULL,NULL,NULL);
        INSERT INTO runs VALUES (2,'beta','low','20261102','v1','schedule','["math","write_zh"]','{}',1,2,120,90,101,'partial',11,0.2,2,NULL,NULL,NULL);
        INSERT INTO runs VALUES (3,'alpha','medium','20261101','v0','schedule','["math"]','{}',1,2,120,80,89,'ok',9,0.1,2,NULL,NULL,NULL);
        INSERT INTO runs VALUES (4,'alpha','high','20261102','v1','schedule','["math"]','{}',1,2,120,90,102,'running',NULL,NULL,2,NULL,NULL,NULL);
         INSERT INTO run_dims VALUES (1,'math',90,12,0,2,3,1,24,100,50,0.1,0.01,NULL,NULL), (1,'logic',80,12,1,3,4,1.5,30,100,50,0.1,0.0125,NULL,NULL), (1,'write_zh',83.3,8,0,14,16,2,84,100,50,0.012,0.012,78,0.003), (1,'write_en',81,8,1,15,18,2.5,90,100,50,0.014,0.017,NULL,0.004), (1,'ui',50,2,0,7,9,1,14,100,50,0.1,0.01,NULL,NULL), (2,'math',70,12,2,5,7,2,40,100,50,0.2,0.02,NULL,NULL), (2,'write_zh',95,8,0,10,12,1.5,60,100,50,0.01,0.01,60,0.002), (2,'ui',50,2,0,8,10,1,16,100,50,0.2,0.02,NULL,NULL), (3,'math',85,12,0,2.5,3.5,1.2,25,100,50,0.1,0.011,NULL,NULL);
        INSERT INTO results VALUES (1,1,'write-zh-1','write_zh',1,NULL,'stop',14,2,1,100,50,10,NULL,NULL,78,20,30,0.2,'reply'), (2,1,'write-en-1','write_en',0,NULL,'stop',15,2.5,1,100,50,10,NULL,NULL,NULL,NULL,NULL,NULL,'reply');
        INSERT INTO ui_samples VALUES (1,1,'classic','pelican bicycle','<svg xmlns="http://www.w3.org/2000/svg"><circle cx="10" cy="10" r="5"/></svg>',1,8,200,100), (2,1,'variant','fox train','<svg/>',1,NULL,NULL,101), (3,2,'classic','pelican bicycle','<svg/>',1,6,201,102), (4,2,'variant','fox train',NULL,0,0,NULL,103);
        """
    )
    db.commit()
    db.close()
    return path
