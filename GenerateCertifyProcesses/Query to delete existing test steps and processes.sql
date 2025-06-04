select * from TestStep where ProcessID IN (Select ProcessID from Process where ProcessFolderID = 404106)

DELETE from TestStepAction where 
	TestStepID IN (SELECT TestStepID from TestStep where ProcessID IN (Select ProcessID from Process where ProcessFolderID = 404106))
DELETE from TestStep where ProcessID IN (Select ProcessID from Process where ProcessFolderID = 404106)
DELETE from Process where ProcessFolderID = 404106