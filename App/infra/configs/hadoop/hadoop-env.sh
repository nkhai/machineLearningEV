#!/usr/bin/env bash
#
# Hadoop environment configuration
# Compatible with: apache/hadoop:3.4.2 (Docker)
# Purpose: DEV / LAB / Airflow + Spark on YARN
# Hardware assumption: ~32GB RAM free, single-node cluster
#

###############################################################################
# JAVA
###############################################################################

# Force Hadoop to use Java 11 (recommended for Hadoop 3.x)
export JAVA_HOME=${JAVA_HOME:-/usr/lib/jvm/java-11-openjdk}

###############################################################################
# Hadoop base directories
###############################################################################

export HADOOP_HOME=/opt/hadoop
export HADOOP_CONF_DIR=${HADOOP_HOME}/etc/hadoop

###############################################################################
# Native libraries
###############################################################################

export HADOOP_COMMON_LIB_NATIVE_DIR=${HADOOP_HOME}/lib/native
export HADOOP_OPTS="-Djava.library.path=${HADOOP_COMMON_LIB_NATIVE_DIR}"

###############################################################################
# Logging
###############################################################################

export HADOOP_LOG_DIR=/opt/hadoop/logs
export YARN_LOG_DIR=/opt/hadoop/logs
export HDFS_LOG_DIR=/opt/hadoop/logs
export MAPRED_LOG_DIR=/opt/hadoop/logs

###############################################################################
# Heap size tuning
# Server: ~32GB RAM
# Topology: 1 NameNode + 1 DataNode + YARN (RM + NM)
###############################################################################

# =========================
# HDFS
# =========================

# NameNode: metadata, RPC, Web UI
export HADOOP_NAMENODE_OPTS="-Xms2g -Xmx4g"

# DataNode: block management, checksum, IO
export HADOOP_DATANODE_OPTS="-Xms2g -Xmx4g"

# SecondaryNameNode: checkpoint only
export HADOOP_SECONDARYNAMENODE_OPTS="-Xms512m -Xmx1g"

# =========================
# YARN
# =========================

# ResourceManager: scheduler, state store
export YARN_RESOURCEMANAGER_OPTS="-Xms1g -Xmx2g"

# NodeManager: container lifecycle, monitoring
export YARN_NODEMANAGER_OPTS="-Xms2g -Xmx4g"

# =========================
# MapReduce Job History
# =========================

export HADOOP_JOB_HISTORYSERVER_OPTS="-Xms512m -Xmx1g"

###############################################################################
# JVM GC tuning (safe for long-running daemons)
###############################################################################

export HADOOP_OPTS="${HADOOP_OPTS} \
-XX:+UseG1GC \
-XX:MaxGCPauseMillis=200 \
-XX:InitiatingHeapOccupancyPercent=45 \
-XX:+ParallelRefProcEnabled \
-XX:+ExitOnOutOfMemoryError"

###############################################################################
# Security (DEV / LAB - NON SECURE MODE)
###############################################################################

# IMPORTANT:
# Do NOT define secure Hadoop users in Docker.
# apache/hadoop image does NOT provide user 'hdfs'.

export HDFS_NAMENODE_USER=
export HDFS_DATANODE_USER=
export HDFS_SECONDARYNAMENODE_USER=

# Force Hadoop to run as current container user
export HADOOP_USER_NAME=root

###############################################################################
# PID directory
###############################################################################

export HADOOP_PID_DIR=/opt/hadoop/pids

###############################################################################
# YARN container execution
###############################################################################

# Default executor (no LinuxContainerExecutor in Docker)
export YARN_CONTAINER_EXECUTOR_CLASS=org.apache.hadoop.yarn.server.nodemanager.DefaultContainerExecutor

###############################################################################
# Network stability (Docker / WSL)
###############################################################################

# Avoid IPv6 / weird Docker DNS issues
export HADOOP_CLIENT_OPTS="-Djava.net.preferIPv4Stack=true"

###############################################################################
# End of file
###############################################################################
