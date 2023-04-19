# Create a program that open a url.txt file
# Then, it wil search for every string that starts with "data-appid=\" and ends with ".\""
# Then, it will save all the appid's in a file called appid.txt, where each appid is in a new line

start_string = '<a href="https://steamcommunity.com/app/'
end_string = '">'
stop_string = '>12.0h<'
PlayGamesLimit = 32

def main():
   TotalGamesFound = 0
   file = open("url.txt", encoding="utf8")
   lines = file.readlines()
   file.close()
   for line in lines:
      start = line.find(start_string)
      end = line.find(end_string)
      if start != -1 and end != -1:
         TotalGamesFound += 1
         if TotalGamesFound == 1:
            appIDsFile = open("appid.txt", "w")
            appIDsFile.write("")
         appid = line[start + len(start_string):end]
         appIDsFile = open("appid.txt", "a")
         if (TotalGamesFound % PlayGamesLimit) == 0 and TotalGamesFound != 1:
            appIDsFile.write(appid + "\n")
         else:
            appIDsFile.write(appid + ",")
      if line.find(stop_string) != -1:
         appIDsFile.close()
         # deleteLastChar()
         break
   print("Total Games Found: " + str(TotalGamesFound))
         
def deleteLastChar():
   appIDsFile = open("appid.txt", "r")
   lines = appIDsFile.readlines()
   # if the last char in the last line is a comma, delete it
   if lines[-1][-1] == ",":
      lines[-1] = lines[-1][:-1]
   appIDsFile = open("D:\Backup\Mega Sync\My Softwares\Windows\Steam ID File\Parzival\ParzivalIDs.txt", "w")
   appIDsFile.write("")
   appIDsFile.writelines(lines)
   appIDsFile.close()
               
if __name__ == "__main__":
   main()