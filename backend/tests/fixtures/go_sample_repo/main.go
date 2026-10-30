package main

import (
	"fmt"

	"github.com/gin-gonic/gin"
	textlang "golang.org/x/text/language"
)

func main() {
	fmt.Println(gin.Mode(), textlang.English)
}
