FROM apache/airflow:3.1.6

USER root

# Cài Java (Hadoop cần)
RUN apt-get update && apt-get install -y --no-install-recommends \
    openjdk-17-jdk \
    curl \
    ca-certificates \
    gcc \
    g++ \
    libsasl2-dev \
    libsasl2-modules \
    libkrb5-dev \
    netcat-openbsd \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Set JAVA_HOME
ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

# Hadoop
ENV HADOOP_VERSION=3.4.2
ENV HADOOP_HOME=/opt/hadoop
RUN curl -fsSL https://downloads.apache.org/hadoop/common/hadoop-$HADOOP_VERSION/hadoop-$HADOOP_VERSION.tar.gz -o /tmp/hadoop.tar.gz \
    && tar -xzf /tmp/hadoop.tar.gz -C /opt/ \
    && mv /opt/hadoop-$HADOOP_VERSION $HADOOP_HOME \
    && rm /tmp/hadoop.tar.gz
ENV PATH=$PATH:$HADOOP_HOME/bin:$HADOOP_HOME/sbin

# Chuyển về user airflow
USER airflow

# Cài Python packages
# PostgreSQL
RUN pip install --no-cache-dir apache-airflow-providers-postgres==6.5.3 psycopg2-binary==2.9.11

# Kafka
RUN pip install --no-cache-dir apache-airflow-providers-apache-kafka==1.11.3 confluent-kafka==2.13.0

# Spark + HDFS
RUN pip install --no-cache-dir apache-airflow-providers-apache-spark==5.5.0 apache-airflow-providers-apache-hdfs==4.11.3

# Celery + Redis
RUN pip install --no-cache-dir apache-airflow-providers-celery==3.15.1 apache-airflow-providers-redis==4.4.2

# ML/DL
RUN pip install --no-cache-dir torch==2.10.0 xgboost==3.1.3 scikit-learn==1.7.2 tensorflow==2.21.0 keras==3.14.0 matplotlib==3.10.8 pyarrow==23.0.0



# WORKDIR /opt/airflow
