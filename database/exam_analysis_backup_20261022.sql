-- MySQL dump 10.13  Distrib 8.0.44, for Win64 (x86_64)
--
-- Host: 127.0.0.1    Database: exam_analysis
-- ------------------------------------------------------
-- Server version	8.0.44

/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!50503 SET NAMES utf8mb4 */;
/*!40103 SET @OLD_TIME_ZONE=@@TIME_ZONE */;
/*!40103 SET TIME_ZONE='+00:00' */;
/*!40014 SET @OLD_UNIQUE_CHECKS=@@UNIQUE_CHECKS, UNIQUE_CHECKS=0 */;
/*!40014 SET @OLD_FOREIGN_KEY_CHECKS=@@FOREIGN_KEY_CHECKS, FOREIGN_KEY_CHECKS=0 */;
/*!40101 SET @OLD_SQL_MODE=@@SQL_MODE, SQL_MODE='NO_AUTO_VALUE_ON_ZERO' */;
/*!40111 SET @OLD_SQL_NOTES=@@SQL_NOTES, SQL_NOTES=0 */;

--
-- Current Database: `exam_analysis`
--

CREATE DATABASE /*!32312 IF NOT EXISTS*/ `exam_analysis` /*!40100 DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci */ /*!80016 DEFAULT ENCRYPTION='N' */;

USE `exam_analysis`;

--
-- Table structure for table `admins`
--

DROP TABLE IF EXISTS `admins`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `admins` (
  `admin_id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(50) NOT NULL,
  `full_name` varchar(100) NOT NULL,
  `password_hash` varchar(255) NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`admin_id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `admins`
--

LOCK TABLES `admins` WRITE;
/*!40000 ALTER TABLE `admins` DISABLE KEYS */;
INSERT INTO `admins` VALUES (1,'admin','System Administrator','scrypt:32768:8:1$mrxP2XLJCUD8eEBn$1f27cb713d3eb0451cfdd6360aa3bedd8f1eddeaf1f08771d79ea23b6bef914b96e92234b71bd9e9d6931bafe60f7ab0bd44f50b0cd1dde41ccae1a015378bc1','2026-08-08 14:50:01');
/*!40000 ALTER TABLE `admins` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `marks`
--

DROP TABLE IF EXISTS `marks`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `marks` (
  `mark_id` int NOT NULL AUTO_INCREMENT,
  `student_id` int NOT NULL,
  `tamil` int NOT NULL,
  `english` int NOT NULL,
  `mathematics` int NOT NULL,
  `science` int NOT NULL,
  `social_science` int NOT NULL,
  `computer_science` int NOT NULL,
  `internal_marks` int NOT NULL,
  `total_marks` int NOT NULL,
  `percentage` decimal(5,2) NOT NULL,
  `grade` varchar(5) NOT NULL,
  `result` varchar(10) NOT NULL,
  `exam_date` date NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`mark_id`),
  KEY `idx_marks_student` (`student_id`),
  KEY `idx_marks_exam_date` (`exam_date`),
  CONSTRAINT `fk_marks_student` FOREIGN KEY (`student_id`) REFERENCES `students` (`student_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `marks`
--

LOCK TABLES `marks` WRITE;
/*!40000 ALTER TABLE `marks` DISABLE KEYS */;
INSERT INTO `marks` VALUES (1,1,96,94,95,93,92,94,92,656,93.71,'A+','Pass','2026-06-15','2026-08-08 14:50:01'),(2,2,88,84,86,83,85,87,80,593,84.71,'A','Pass','2026-06-15','2026-08-08 14:50:01'),(3,3,74,72,70,76,71,73,68,504,72.00,'B+','Pass','2026-06-15','2026-08-08 14:50:01'),(4,4,91,89,93,90,92,94,88,637,91.00,'A+','Pass','2026-06-15','2026-08-08 14:50:01'),(5,5,63,61,65,60,64,62,58,433,61.86,'B','Pass','2026-06-15','2026-08-08 14:50:01'),(6,6,82,80,84,81,83,79,77,566,80.86,'A','Pass','2026-06-15','2026-08-08 14:50:01'),(7,7,55,57,52,54,56,53,50,377,53.86,'C','Pass','2026-06-15','2026-08-08 14:50:01'),(8,8,97,96,98,95,94,97,96,673,96.14,'A+','Pass','2026-06-15','2026-08-08 14:50:01'),(9,9,78,75,77,74,76,79,72,531,75.86,'A','Pass','2026-06-15','2026-08-08 14:50:01'),(10,10,68,66,70,67,69,65,60,465,66.43,'B','Pass','2026-06-15','2026-08-08 14:50:01'),(11,11,85,83,87,84,86,82,81,588,84.00,'A','Pass','2026-06-15','2026-08-08 14:50:01'),(12,12,92,90,91,93,89,94,90,639,91.29,'A+','Pass','2026-06-15','2026-08-08 14:50:01'),(13,13,41,38,42,39,40,37,35,272,38.86,'F','Fail','2026-06-15','2026-08-08 14:50:01'),(14,14,71,73,72,70,74,69,66,495,70.71,'B+','Pass','2026-06-15','2026-08-08 14:50:01'),(15,15,59,58,60,57,61,56,55,406,58.00,'C','Pass','2026-06-15','2026-08-08 14:50:01'),(16,16,94,92,95,93,91,96,89,650,92.86,'A+','Pass','2026-06-15','2026-08-08 14:50:01'),(17,17,47,49,45,46,44,48,42,321,45.86,'D','Fail','2026-06-15','2026-08-08 14:50:01'),(18,18,86,88,84,87,85,89,82,601,85.86,'A','Pass','2026-06-15','2026-08-08 14:50:01'),(19,19,36,34,38,35,37,33,30,243,34.71,'F','Fail','2026-06-15','2026-08-08 14:50:01'),(20,20,79,81,78,80,77,82,75,552,78.86,'B+','Pass','2026-06-15','2026-08-08 14:50:01');
/*!40000 ALTER TABLE `marks` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `predictions`
--

DROP TABLE IF EXISTS `predictions`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `predictions` (
  `prediction_id` int NOT NULL AUTO_INCREMENT,
  `student_id` int NOT NULL,
  `predicted_percentage` decimal(5,2) NOT NULL,
  `predicted_grade` varchar(5) NOT NULL,
  `predicted_result` varchar(10) NOT NULL,
  `performance_level` varchar(20) NOT NULL,
  `prediction_date` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`prediction_id`),
  KEY `idx_prediction_student` (`student_id`),
  CONSTRAINT `fk_predictions_student` FOREIGN KEY (`student_id`) REFERENCES `students` (`student_id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `predictions`
--

LOCK TABLES `predictions` WRITE;
/*!40000 ALTER TABLE `predictions` DISABLE KEYS */;
/*!40000 ALTER TABLE `predictions` ENABLE KEYS */;
UNLOCK TABLES;

--
-- Table structure for table `students`
--

DROP TABLE IF EXISTS `students`;
/*!40101 SET @saved_cs_client     = @@character_set_client */;
/*!50503 SET character_set_client = utf8mb4 */;
CREATE TABLE `students` (
  `student_id` int NOT NULL AUTO_INCREMENT,
  `register_number` varchar(50) NOT NULL,
  `student_name` varchar(100) NOT NULL,
  `email` varchar(120) NOT NULL,
  `phone` varchar(20) NOT NULL,
  `gender` enum('Male','Female','Other') NOT NULL,
  `department` varchar(100) NOT NULL,
  `year` tinyint NOT NULL,
  `semester` tinyint NOT NULL,
  `attendance_percentage` decimal(5,2) NOT NULL DEFAULT '0.00',
  `password_hash` varchar(255) NOT NULL,
  `created_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at` timestamp NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`student_id`),
  UNIQUE KEY `register_number` (`register_number`),
  UNIQUE KEY `email` (`email`),
  KEY `idx_student_name` (`student_name`),
  KEY `idx_student_department` (`department`),
  KEY `idx_student_year_semester` (`year`,`semester`)
) ENGINE=InnoDB AUTO_INCREMENT=21 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci;
/*!40101 SET character_set_client = @saved_cs_client */;

--
-- Dumping data for table `students`
--

LOCK TABLES `students` WRITE;
/*!40000 ALTER TABLE `students` DISABLE KEYS */;
INSERT INTO `students` VALUES (1,'REG2026001','Aarav Kumar','aarav.kumar@example.com','9000000001','Male','Computer Science',3,5,96.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(2,'REG2026002','Diya Sharma','diya.sharma@example.com','9000000002','Female','Electronics',2,4,88.50,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(3,'REG2026003','Rahul Singh','rahul.singh@example.com','9000000003','Male','Mechanical',4,8,72.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(4,'REG2026004','Priya Nair','priya.nair@example.com','9000000004','Female','Information Technology',1,2,91.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(5,'REG2026005','Vikram Patel','vikram.patel@example.com','9000000005','Male','Civil',3,6,64.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(6,'REG2026006','Meera Iyer','meera.iyer@example.com','9000000006','Female','Computer Science',4,7,84.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(7,'REG2026007','Karan Mehta','karan.mehta@example.com','9000000007','Male','Electrical',2,3,58.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(8,'REG2026008','Ananya Rao','ananya.rao@example.com','9000000008','Female','Mechanical',1,1,97.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(9,'REG2026009','Arjun Das','arjun.das@example.com','9000000009','Male','Electronics',4,8,76.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(10,'REG2026010','Sneha Kapoor','sneha.kapoor@example.com','9000000010','Female','Information Technology',2,4,66.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(11,'REG2026011','Mohammed Ali','mohammed.ali@example.com','9000000011','Male','Civil',3,5,81.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(12,'REG2026012','Nisha Verma','nisha.verma@example.com','9000000012','Female','Computer Science',4,7,92.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(13,'REG2026013','Suresh Reddy','suresh.reddy@example.com','9000000013','Male','Electrical',1,2,49.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(14,'REG2026014','Lakshmi Menon','lakshmi.menon@example.com','9000000014','Female','Mechanical',2,3,73.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(15,'REG2026015','Rohit Jain','rohit.jain@example.com','9000000015','Male','Information Technology',3,6,55.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(16,'REG2026016','Keerthana S','keerthana.s@example.com','9000000016','Female','Civil',4,8,94.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(17,'REG2026017','Imran Khan','imran.khan@example.com','9000000017','Male','Electronics',2,4,61.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(18,'REG2026018','Divya Prakash','divya.prakash@example.com','9000000018','Female','Computer Science',1,1,87.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(19,'REG2026019','Asha Balan','asha.balan@example.com','9000000019','Female','Electrical',3,5,45.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01'),(20,'REG2026020','Yash Thakur','yash.thakur@example.com','9000000020','Male','Civil',4,7,78.00,'scrypt:32768:8:1$yUssd7XLZysLNG5c$1ed2456cc6a83681b753f8c50620653f08b12afe86373987d74ab2e7f9fe2d9fa9afec1a231562d2139c0567b92b79cecc1d70274389f9a2c9980b8090aeb4ad','2026-08-08 14:50:01','2026-08-08 14:50:01');
/*!40000 ALTER TABLE `students` ENABLE KEYS */;
UNLOCK TABLES;
/*!40103 SET TIME_ZONE=@OLD_TIME_ZONE */;

/*!40101 SET SQL_MODE=@OLD_SQL_MODE */;
/*!40014 SET FOREIGN_KEY_CHECKS=@OLD_FOREIGN_KEY_CHECKS */;
/*!40014 SET UNIQUE_CHECKS=@OLD_UNIQUE_CHECKS */;
/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
/*!40111 SET SQL_NOTES=@OLD_SQL_NOTES */;

-- Dump completed on 2026-10-22 15:34:38
