module github.com/verspect/go-sample

go 1.22

require (
	github.com/gin-gonic/gin v1.10.0
	github.com/old/module v1.2.0
	golang.org/x/text v0.16.0 // indirect
)

replace github.com/old/module => github.com/new/module v1.3.0
